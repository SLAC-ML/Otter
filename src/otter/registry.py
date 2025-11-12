"""
Otter Application Registry Configuration

This module defines the component registry for the Otter Badger optimization run assistant.
All Otter-specific capabilities, context classes, and data sources are declared here.
"""

from osprey.registry import (
    extend_framework_registry,
    CapabilityRegistration,
    ContextClassRegistration,
    DataSourceRegistration,
    FrameworkPromptProviderRegistration,
    ProviderRegistration,
    RegistryConfigProvider,
)


class OtterRegistryProvider(RegistryConfigProvider):
    """Registry provider for Otter application."""

    def get_registry_config(self):
        """
        Get Otter application registry configuration.

        Uses extend_framework_registry() to automatically include framework
        capabilities alongside Otter-specific components.

        Returns:
            RegistryConfig: Complete registry with framework + Otter components
        """
        return extend_framework_registry(
            # ====================
            # Providers
            # ====================
            # Custom LLM provider adapters for Otter
            providers=[
                ProviderRegistration(
                    module_path="otter.providers.stanford",
                    class_name="StanfordProviderAdapter",
                )
            ],
            # ====================
            # Capabilities
            # ====================
            capabilities=[
                CapabilityRegistration(
                    name="extract_run_filters",
                    module_path="otter.capabilities.extract_run_filters",
                    class_name="ExtractRunFiltersCapability",
                    description="Extract structured run query filters from natural language",
                    provides=["RUN_QUERY_FILTERS"],
                    requires=[],
                ),
                CapabilityRegistration(
                    name="query_runs",
                    module_path="otter.capabilities.query_runs",
                    class_name="QueryRunsCapability",
                    description="Query Badger optimization runs from archive using filters from extract_run_filters",
                    provides=["BADGER_RUNS"],  # Returns container with multiple runs
                    requires=["RUN_QUERY_FILTERS"],
                ),
                CapabilityRegistration(
                    name="analyze_runs",
                    module_path="otter.capabilities.analyze_runs",
                    class_name="AnalyzeRunsCapability",
                    description="Analyze and compare multiple runs",
                    provides=["RUN_ANALYSIS"],
                    requires=["BADGER_RUNS"],  # Updated to use BADGER_RUNS container
                ),
                CapabilityRegistration(
                    name="propose_routines",
                    module_path="otter.capabilities.propose_routines",
                    class_name="ProposeRoutinesCapability",
                    description="Generate executable Badger routine YAML from successful runs",
                    provides=["BADGER_ROUTINES"],
                    requires=["BADGER_RUNS", "RUN_ANALYSIS"],  # Requires BOTH for complete VOCS + selection
                ),
                # Future capabilities:
                # - search_runs: Find runs matching complex criteria (VOCS-based filtering)
                # - infer_terminology: Map ambiguous terms to actual objective/variable names
                # - compose_routine: Generate complete Badger routine from specifications
            ],
            # ====================
            # Context Classes
            # ====================
            context_classes=[
                ContextClassRegistration(
                    context_type="RUN_QUERY_FILTERS",
                    module_path="otter.context_classes",
                    class_name="RunQueryFilters",
                ),
                ContextClassRegistration(
                    context_type="BADGER_RUN",
                    module_path="otter.context_classes",
                    class_name="BadgerRunContext",
                ),
                ContextClassRegistration(
                    context_type="BADGER_RUNS",
                    module_path="otter.context_classes",
                    class_name="BadgerRunsContext",
                ),
                ContextClassRegistration(
                    context_type="RUN_ANALYSIS",
                    module_path="otter.context_classes",
                    class_name="RunAnalysisContext",
                ),
                ContextClassRegistration(
                    context_type="BADGER_ROUTINES",
                    module_path="otter.context_classes",
                    class_name="BadgerRoutinesContext",
                ),
                # Legacy context (kept for backward compatibility):
                ContextClassRegistration(
                    context_type="ROUTINE_PROPOSAL",
                    module_path="otter.context_classes",
                    class_name="RoutineProposalContext",
                ),
            ],
            # ====================
            # Data Sources
            # ====================
            data_sources=[
                DataSourceRegistration(
                    name="badger_archive",
                    module_path="otter.data_sources.badger_archive",
                    class_name="BadgerArchiveDataSource",
                    description="Badger optimization runs archive with health monitoring",
                    health_check_required=True,
                )
            ],
            # ====================
            # Framework Prompt Providers
            # ====================
            # Otter-specific prompts inject Bayesian Optimization domain knowledge
            framework_prompt_providers=[
                FrameworkPromptProviderRegistration(
                    application_name="otter",
                    module_path="otter.framework_prompts",
                    description="Otter-specific framework prompts with Badger/BO domain knowledge for correct run analysis",
                    prompt_builders={
                        "response_generation": "OtterResponseGenerationPromptBuilder",
                        "orchestrator": "OtterOrchestratorPromptBuilder",
                    },
                )
            ],
            # ====================
            # Framework Exclusions
            # ====================
            # Optional: Use exclude_capabilities parameter to disable framework components
            # Example: exclude_capabilities=["python"] to disable Python execution capability
            # Currently no exclusions needed - Otter works alongside all framework capabilities
        )
