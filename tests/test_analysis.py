from sdlc_agents.analysis import analyze, plan_agents


def test_analyze_extracts_operations_and_requirements():
    spec = analyze(
        instruction="Create and validate customer orders, then generate a report.",
        input_expectations="JSON order with id and items",
        output_expectations="Processed order and a summary report",
        language="python",
    )
    assert spec.title
    assert spec.slug
    assert spec.operations  # verbs detected
    assert any("create" in o or "validate" in o or "generate" in o for o in spec.operations)
    assert spec.functional_requirements
    # Baseline NFRs always present.
    assert any("offline" in n.lower() for n in spec.nonfunctional_requirements)
    assert any("confidential" in n.lower() for n in spec.nonfunctional_requirements)
    assert len(spec.components) >= 4


def test_analyze_handles_empty_instruction():
    spec = analyze("", "", "", "python")
    assert spec.title
    assert spec.operations  # falls back to defaults
    assert spec.functional_requirements


def test_plan_agents_returns_three_roles_with_prompts():
    spec = analyze("Build a calculator that adds and subtracts numbers.", "two numbers", "the result")
    plans = plan_agents(spec)
    ids = {p.agent_id for p in plans}
    assert ids == {"architect", "developer", "validation_engineer"}
    for p in plans:
        assert p.role_title
        assert p.role_description
        assert p.tasks
        assert p.prompt
        assert spec.title in p.prompt


def test_context_is_json_serialisable():
    import json

    spec = analyze("Store and fetch documents securely.", "a document", "stored document id")
    json.dumps(spec.to_context())  # must not raise
