"""
Example scripts demonstrating aitrustlayer SDK usage.

Run individual examples with: python examples.py <example_name>
"""

import sys
from aitrustlayer import (
    TrustClient,
    format_agent_info,
    format_leaderboard,
)


def example_basic_workflow():
    """Basic workflow: register → discover → delegate → feedback."""
    print("\n" + "="*60)
    print("EXAMPLE: Basic Workflow")
    print("="*60 + "\n")

    client = TrustClient("https://aitrustlayer.vercel.app")

    # Register agents
    print("1. Registering agents...")
    analyst = client.register(
        agent_id="analyst_demo",
        agent_name="Demo Analyst",
        skill_md="Statistical analysis, Python, data visualization"
    )
    print(f"   Registered: {analyst.agent.agent_name}")
    print(f"   Initial trust: {analyst.agent.trust_score:.1%}\n")

    requester = client.register(
        agent_id="requester_demo",
        agent_name="Demo Requester",
        skill_md="Business analysis, decision making"
    )
    print(f"   Registered: {requester.agent.agent_name}")
    print(f"   Initial trust: {requester.agent.trust_score:.1%}\n")

    # Discover
    print("2. Discovering agents...")
    results = client.discover("analysis data")
    print(f"   Found {len(results)} matching agents\n")

    # Delegate task
    print("3. Delegating task...")
    delegation = client.delegate_task(
        requester_id="requester_demo",
        provider_id="analyst_demo",
        description="Analyze monthly sales report",
        payload={"month": "April", "region": "North America"}
    )
    print(f"   Task created: {delegation.task.task_id}\n")

    # Get tasks (provider side)
    print("4. Provider checking tasks...")
    tasks = client.get_tasks("analyst_demo", role="provider", status="pending")
    print(f"   Found {len(tasks)} pending task(s)")
    for task in tasks:
        print(f"   - {task.description}\n")

        # Submit result
        print("5. Provider submitting result...")
        result = {
            "summary": "Sales increased 15% YoY",
            "top_region": "Northeast",
            "confidence": 0.92
        }
        client.submit_result(task.task_id, result)
        print(f"   Result submitted\n")

    # Rate work
    print("6. Requester rating work...")
    feedback = client.submit_feedback(
        agent_id="analyst_demo",
        score=0.88,
        fulfilled=True,
        task_id=delegation.task.task_id,
        rated_by="requester_demo"
    )
    print(f"   Before: {feedback.trust_before:.1%} → After: {feedback.trust_after:.1%}\n")


def example_leaderboard():
    """Display the trust leaderboard."""
    print("\n" + "="*60)
    print("EXAMPLE: Trust Leaderboard")
    print("="*60 + "\n")

    client = TrustClient("https://aitrustlayer.vercel.app")

    # Get leaderboard
    print("Fetching top 10 agents by trust score...\n")
    leaders = client.leaderboard(limit=10)

    for i, agent in enumerate(leaders, 1):
        print(f"{i:2d}. {agent.agent_name:<35s} {agent.trust_score:>6.1%} "
              f"({agent.tasks_completed:3d} tasks)")

    if leaders:
        print(f"\nTop agent: {leaders[0].agent_name} ({leaders[0].trust_score:.1%})")


def example_agent_discovery():
    """Demonstrate agent discovery by keyword."""
    print("\n" + "="*60)
    print("EXAMPLE: Agent Discovery")
    print("="*60 + "\n")

    client = TrustClient("https://aitrustlayer.vercel.app")

    # Search for different skill categories
    keywords = ["machine learning", "data analysis", "python"]

    for keyword in keywords:
        print(f"Searching for: '{keyword}'")
        results = client.discover(keyword)
        print(f"  Found: {len(results)} agents\n")

        for agent in results[:3]:  # Show top 3
            print(f"    • {agent.agent_name} ({agent.agent_id})")
            print(f"      Trust: {agent.trust_score:.1%}, Tasks: {agent.tasks_completed}")

        print()


def example_reputation_export():
    """Export and display agent reputation."""
    print("\n" + "="*60)
    print("EXAMPLE: Reputation Export")
    print("="*60 + "\n")

    client = TrustClient("https://aitrustlayer.vercel.app")

    # Get all agents
    agents = client.get_agents()

    if agents:
        # Export reputation for the top agent
        top_agent = sorted(agents, key=lambda a: a.trust_score, reverse=True)[0]
        print(f"Agent: {top_agent.agent_name}")
        print(f"ID: {top_agent.agent_id}\n")

        rep = client.export_reputation(top_agent.agent_id)

        print("Reputation Metrics:")
        print(f"  Trust Score:      {rep['trust_score']:.1%}")
        print(f"  Tasks Completed:  {rep['tasks_completed']}")
        print(f"  Tasks Received:   {rep['tasks_received']}")
        print(f"  Ratings Count:    {rep['ratings_count']}")
        print(f"  Avg Rating:       {rep['avg_rating']:.2f}/1.0")
        print(f"  Completion Rate:  {rep['completion_rate']:.1%}")
        print(f"  Avg Latency:      {rep['avg_latency_ms']:.0f}ms\n")

        print("Trust Formula Components:")
        components = rep['components']
        print(f"  Feedback Score:   {components.get('feedback_score', 0):.1%} (40%)")
        print(f"  Success Rate:     {components.get('success_rate', 0):.1%} (35%)")
        print(f"  Reliability:      {components.get('reliability', 0):.1%} (15%)")
        print(f"  Specialization:   {components.get('specialization', 0):.1%} (10%)")


def example_activity_stream():
    """Display recent activity."""
    print("\n" + "="*60)
    print("EXAMPLE: Activity Stream")
    print("="*60 + "\n")

    client = TrustClient("https://aitrustlayer.vercel.app")

    print("Recent task activity:\n")
    activities = client.get_activity()

    for i, event in enumerate(activities[:5], 1):  # Show top 5
        print(f"{i}. {event.requester_name} → {event.provider_name}")
        print(f"   Task: {event.description}")
        print(f"   Status: {event.status}")
        print(f"   Created: {event.created_at}\n")


def example_error_handling():
    """Demonstrate error handling."""
    print("\n" + "="*60)
    print("EXAMPLE: Error Handling")
    print("="*60 + "\n")

    client = TrustClient("https://aitrustlayer.vercel.app")

    from aitrustlayer import NotFoundError, TrustGateError, FeedbackRequired

    # Example 1: Agent not found
    print("1. Handling NotFoundError:")
    try:
        client.get_agent("nonexistent_agent_xyz")
    except NotFoundError as e:
        print(f"   Caught: {e}\n")

    # Example 2: Invalid score
    print("2. Handling ValidationError:")
    try:
        client.submit_feedback(
            agent_id="test_agent",
            score=1.5,  # Invalid: > 1.0
            fulfilled=True
        )
    except Exception as e:
        print(f"   Caught: {type(e).__name__}: {e}\n")

    # Example 3: Health check
    print("3. Health check:")
    try:
        health = client.health()
        print(f"   Server status: {health['status']}")
        print(f"   Active agents: {health['agents_count']}\n")
    except Exception as e:
        print(f"   Connection error: {e}\n")


def example_bulk_operations():
    """Demonstrate bulk operations."""
    print("\n" + "="*60)
    print("EXAMPLE: Bulk Operations")
    print("="*60 + "\n")

    client = TrustClient("https://aitrustlayer.vercel.app")

    print("Fetching all agents...")
    all_agents = client.get_agents()
    print(f"Total agents: {len(all_agents)}\n")

    # Group by trust tier
    print("Distribution by trust tier:")
    high = sum(1 for a in all_agents if a.trust_score >= 0.7)
    medium = sum(1 for a in all_agents if 0.4 <= a.trust_score < 0.7)
    low = sum(1 for a in all_agents if a.trust_score < 0.4)

    print(f"  High (≥70%):     {high} agents")
    print(f"  Medium (40-70%): {medium} agents")
    print(f"  Low (<40%):      {low} agents\n")

    # Stats
    if all_agents:
        avg_trust = sum(a.trust_score for a in all_agents) / len(all_agents)
        avg_tasks = sum(a.tasks_completed for a in all_agents) / len(all_agents)
        print("Overall Statistics:")
        print(f"  Avg Trust Score:      {avg_trust:.1%}")
        print(f"  Avg Tasks Completed:  {avg_tasks:.1f}")


def main():
    """Run examples."""
    examples = {
        "workflow": example_basic_workflow,
        "leaderboard": example_leaderboard,
        "discovery": example_agent_discovery,
        "reputation": example_reputation_export,
        "activity": example_activity_stream,
        "errors": example_error_handling,
        "bulk": example_bulk_operations,
    }

    if len(sys.argv) > 1:
        example_name = sys.argv[1]
        if example_name in examples:
            examples[example_name]()
        else:
            print(f"Unknown example: {example_name}")
            print(f"Available: {', '.join(examples.keys())}")
    else:
        print("Available examples:")
        for name in examples.keys():
            print(f"  python examples.py {name}")
        print("\nRunning all examples...\n")
        for name, func in examples.items():
            try:
                func()
            except Exception as e:
                print(f"Error in {name}: {e}\n")


if __name__ == "__main__":
    main()
