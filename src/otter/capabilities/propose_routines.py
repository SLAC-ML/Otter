"""
Propose Routines Capability

Capability for generating executable Badger routine YAML from successful runs.
Uses BOTH RUN_ANALYSIS (for selection) and BADGER_RUNS (for complete VOCS data).
"""

import logging
import textwrap
from typing import Dict, Any, Optional
import badger

# Framework imports
from osprey.base.decorators import capability_node
from osprey.base.capability import BaseCapability
from osprey.base.errors import ErrorClassification, ErrorSeverity
from osprey.base.examples import (
    OrchestratorGuide,
    OrchestratorExample,
    TaskClassifierGuide,
    ClassifierExample,
    ClassifierActions,
)
from osprey.base.planning import PlannedStep
from osprey.state import AgentState, StateManager
from osprey.registry import get_registry
from osprey.context.context_manager import ContextManager
from osprey.utils.logger import get_logger
from osprey.utils.streaming import get_streamer

# Badger imports
from badger.utils import get_yaml_string

logger = get_logger("otter", "propose_routines")
registry = get_registry()


# ====================
# Custom Exceptions
# ====================


class ProposeRoutinesError(Exception):
    """Base class for propose routines errors."""

    pass


class InsufficientContextError(ProposeRoutinesError):
    """Raised when not enough context provided for routine generation."""

    pass


# ====================
# Helper Functions
# ====================


def convert_vocs_from_run_context(run):
    """
    Convert BadgerRunContext VOCS format to Badger routine dict format.

    Args:
        run: BadgerRunContext with variables/objectives/constraints

    Returns:
        dict: VOCS dict ready for Badger routine
    """
    # Convert variables from [{name: [min, max]}, ...] to {name: [min, max], ...}
    variables = {}
    for var_dict in run.variables:
        for var_name, var_range in var_dict.items():
            variables[var_name] = var_range

    # Convert objectives from [{name: direction}, ...] to {name: direction, ...}
    objectives = {}
    for obj_dict in run.objectives:
        for obj_name, direction in obj_dict.items():
            objectives[obj_name] = direction

    # Constraints (currently minimal support)
    constraints = {}
    # TODO: Extract constraint details if needed in future

    vocs_dict = {
        "variables": variables,
        "objectives": objectives,
        "constraints": constraints,
        "constants": {},
        "observables": [],
    }

    return vocs_dict


def compose_routine_from_run(run, name_override: Optional[str] = None):
    """
    Create complete Badger routine dict from a BadgerRunContext.

    Args:
        run: BadgerRunContext from successful optimization
        name_override: Optional custom name for the routine

    Returns:
        dict: Complete routine dict ready to serialize to YAML
    """
    # Get VOCS
    vocs_dict = convert_vocs_from_run_context(run)

    # Compose routine dict with safe defaults
    routine_dict = {
        "name": name_override or f"{run.run_name}-proposed",
        "description": f"Routine based on successful run: {run.run_name}\n"
        f"Algorithm: {run.algorithm}, Beamline: {run.beamline}\n"
        f"Generated from optimization run with {run.num_evaluations} evaluations.",
        # Environment
        "environment": {
            "name": run.badger_environment,
            "params": {},  # Empty for now - user must configure
        },
        # VOCS
        "vocs": vocs_dict,
        # Generator
        "generator": {
            "name": run.algorithm,
            # Default params - could be enhanced to extract from original run
        },
        # Initial points - use current machine state
        "initial_points": None,  # Will use initial_point_actions instead
        # Safety settings
        "relative_to_current": True,  # Safe default: work relative to current state
        "initial_point_actions": [{"type": "add_curr"}],  # Start from current machine state
        # Constraints
        "critical_constraint_names": [],
        # Advanced (using defaults)
        "vrange_limit_options": None,
        "vrange_hard_limit": {},
        # Metadata
        "badger_version": badger.__version__,
    }

    return routine_dict


def serialize_routine_to_yaml(routine_dict: dict) -> str:
    """
    Convert routine dict to YAML string using Badger's serializer.

    Args:
        routine_dict: Complete routine dictionary

    Returns:
        str: YAML string ready to save or execute
    """
    yaml_string = get_yaml_string(routine_dict)
    return yaml_string


# ====================
# Capability Definition
# ====================


@capability_node
class ProposeRoutinesCapability(BaseCapability):
    """
    Generate executable Badger routine YAML from successful runs.

    This capability takes BOTH:
    - BADGER_RUNS: To access complete VOCS (variables with ranges)
    - RUN_ANALYSIS: To identify top performers

    Outputs complete, executable Badger routine YAML strings.
    """

    name = "propose_routines"
    description = "Generate executable Badger routine YAML from successful runs"
    provides = ["BADGER_ROUTINES"]
    requires = ["BADGER_RUNS", "RUN_ANALYSIS"]

    @staticmethod
    async def execute(state: AgentState, **kwargs) -> Dict[str, Any]:
        """Execute routine generation from runs and analysis."""

        step = StateManager.get_current_step(state)
        streamer = get_streamer("propose_routines", state)

        try:
            # Get context manager and parameters
            context_manager = ContextManager(state)
            step_parameters = step.get("parameters", {})

            # Extract parameters
            num_routines = int(step_parameters.get("num_routines", 1))  # Default: 1 routine

            # Get contexts from inputs
            step_inputs = step.get("inputs", [])
            if not step_inputs:
                raise InsufficientContextError("No input contexts provided")

            runs_context = None
            analysis_context = None

            for input_item in step_inputs:
                if "BADGER_RUNS" in input_item:
                    runs_key = input_item["BADGER_RUNS"]
                    runs_context = context_manager.get_context(
                        registry.context_types.BADGER_RUNS, runs_key
                    )
                if "RUN_ANALYSIS" in input_item:
                    analysis_key = input_item["RUN_ANALYSIS"]
                    analysis_context = context_manager.get_context(
                        registry.context_types.RUN_ANALYSIS, analysis_key
                    )

            if not runs_context:
                raise InsufficientContextError("No BADGER_RUNS context found")

            if not analysis_context:
                raise InsufficientContextError("No RUN_ANALYSIS context found")

            streamer.status("Selecting top performer from analysis...")

            # Get top performers from analysis
            analysis_data = analysis_context.analysis_data
            success_patterns = analysis_data.get("success_patterns", {})
            top_performers = success_patterns.get("top_performers", [])

            if not top_performers:
                raise InsufficientContextError("No top performers found in analysis")

            # Select best performer
            best_performer = top_performers[0]
            target_run_name = best_performer["run_name"]

            streamer.status(f"Generating routine from run: {target_run_name}...")

            # Find corresponding run in BADGER_RUNS
            selected_run = None
            for run in runs_context.runs:
                if run.run_name == target_run_name:
                    selected_run = run
                    break

            if not selected_run:
                # Fallback: use first run if exact match not found
                logger.warning(
                    f"Top performer '{target_run_name}' not found in loaded runs, using first available run"
                )
                selected_run = runs_context.runs[0]

            # Compose routine from selected run
            streamer.status("Composing routine with VOCS from run...")
            routine_dict = compose_routine_from_run(selected_run)

            # Serialize to YAML
            streamer.status("Converting to Badger YAML format...")
            routine_yaml = serialize_routine_to_yaml(routine_dict)

            # Build generation metadata
            generation_metadata = {
                "source_runs": [selected_run.run_name],
                "selected_from_analysis": True,
                "top_performer_improvement": best_performer.get("improvement_pct", 0),
                "algorithm": selected_run.algorithm,
                "beamline": selected_run.beamline,
                "badger_environment": selected_run.badger_environment,
                "num_variables": len(selected_run.variables),
                "num_objectives": len(selected_run.objectives),
                "method": "from_top_performer",
            }

            streamer.status("Routine generated successfully!")
            logger.success(f"Generated routine from run: {selected_run.run_name}")

            # Create and store context
            from otter.context_classes import BadgerRoutinesContext

            routines_context = BadgerRoutinesContext(
                routines=[routine_yaml], generation_metadata=generation_metadata
            )

            context_key = step.get("context_key", "badger_routines")
            return StateManager.store_context(
                state, registry.context_types.BADGER_ROUTINES, context_key, routines_context
            )

        except InsufficientContextError as e:
            logger.error(f"Insufficient context: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error generating routine: {e}")
            import traceback

            traceback.print_exc()
            raise

    @staticmethod
    def classify_error(exc: Exception, context: dict) -> ErrorClassification:
        """Error classification for propose routines capability."""

        if isinstance(exc, InsufficientContextError):
            return ErrorClassification(
                severity=ErrorSeverity.CRITICAL,
                user_message=f"Cannot generate routine: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Ensure both BADGER_RUNS and RUN_ANALYSIS contexts are provided",
                },
            )
        else:
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Routine generation error: {str(exc)}",
                metadata={"technical_details": str(exc)},
            )

    def _create_orchestrator_guide(self) -> Optional[OrchestratorGuide]:
        """Create guide for orchestrator."""

        example = OrchestratorExample(
            step=PlannedStep(
                context_key="badger_routines",
                capability="propose_routines",
                task_objective="Generate executable Badger routine from top performer",
                expected_output="BADGER_ROUTINES",
                success_criteria="Routine YAML generated",
                inputs=[{"BADGER_RUNS": "recent_runs"}, {"RUN_ANALYSIS": "run_analysis"}],
                parameters={"num_routines": 1},
            ),
            scenario_description="Generate routine YAML from analyzed runs",
            notes="Requires BOTH BADGER_RUNS (for VOCS) and RUN_ANALYSIS (for selection)",
        )

        return OrchestratorGuide(
            instructions=textwrap.dedent(
                """
                **When to use propose_routines:**
                - User asks to create/propose a routine
                - User wants to generate a Badger routine configuration

                **CRITICAL: Requires BOTH inputs!**
                - BADGER_RUNS: Contains complete VOCS (variable ranges)
                - RUN_ANALYSIS: Identifies best runs to base routine on

                **Workflow:**
                Step 1: query_runs - Load recent runs (output: BADGER_RUNS)
                Step 2: analyze_runs - Analyze patterns (input: BADGER_RUNS, output: RUN_ANALYSIS)
                Step 3: propose_routines - Generate routine (inputs: [BADGER_RUNS, RUN_ANALYSIS])
                Step 4: respond - Show routine to user

                **Input:** BADGER_RUNS + RUN_ANALYSIS contexts
                **Output:** BADGER_ROUTINES (executable YAML strings)
                """
            ).strip(),
            examples=[example],
            priority=7,
        )

    def _create_classifier_guide(self) -> Optional[TaskClassifierGuide]:
        """Create classifier guide."""
        return TaskClassifierGuide(
            instructions="Identify routine generation requests.",
            examples=[
                ClassifierExample(
                    query="Create a routine", result=True, reason="Direct routine request"
                ),
                ClassifierExample(
                    query="Propose a routine for lcls",
                    result=True,
                    reason="Routine generation request",
                ),
                ClassifierExample(
                    query="Show me recent runs", result=False, reason="Query, not generation"
                ),
            ],
            actions_if_true=ClassifierActions(),
        )
