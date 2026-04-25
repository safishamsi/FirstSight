from dotenv import load_dotenv

from app.agent_factory import build_agent
from app.config import get_settings

load_dotenv()


async def create_agent(**kwargs: object) -> object:
    del kwargs
    return build_agent(get_settings())


async def join_call(agent: object, call_type: str, call_id: str, **kwargs: object) -> None:
    del kwargs
    call = await agent.create_call(call_type, call_id)
    async with agent.join(call):
        await agent.simple_response(
            "Say hello and explain that this is the droopdetection realtime backend starter."
        )
        await agent.finish()


if __name__ == "__main__":
    from vision_agents.core import AgentLauncher, Runner

    Runner(
        AgentLauncher(
            create_agent=create_agent,
            join_call=join_call,
        )
    ).cli()

