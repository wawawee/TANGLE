import asyncio
import time
import os
import logging

logger = logging.getLogger("sami.browser")

try:
    from browser_use import Agent as BrowserAgent
    from browser_use.browser.browser import Browser
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BrowserAgent = None
    Browser = None
    BROWSER_USE_AVAILABLE = False


def get_default_llm():
    """Create an LLM for browser-use. Tries Ollama, then OpenRouter, then Gemini."""
    from browser_use.llm.ollama.chat import ChatOllama
    try:
        llm = ChatOllama(model="llama3.2:3b")
        return llm
    except Exception:
        pass

    from browser_use.llm.openai.chat import ChatOpenAI
    or_key = os.getenv("OPENROUTER_API_KEY")
    if or_key:
        return ChatOpenAI(
            model="google/gemini-2.0-flash-001:free",
            base_url="https://openrouter.ai/api/v1",
            api_key=or_key,
        )

    gm_key = os.getenv("GEMINI_API_KEY")
    if gm_key:
        return ChatOpenAI(
            model="gemini-2.0-flash",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=gm_key,
        )

    return None


async def run_browser_task(task: str, llm=None, max_steps: int = 25, headless: bool = True) -> dict:
    if not BROWSER_USE_AVAILABLE:
        return {"success": False, "error": "browser-use not installed. Run: pip install browser-use"}

    if llm is None:
        llm = get_default_llm()
    if llm is None:
        return {"success": False, "error": "No LLM available. Install an Ollama model (ollama pull llama3.2:3b) or set OPENROUTER_API_KEY or GEMINI_API_KEY"}

    browser = None
    start = time.time()

    try:
        if Browser is not None:
            browser = Browser(headless=headless)

        agent = BrowserAgent(
            task=task,
            llm=llm,
            browser=browser,
            use_vision=True,
            max_actions_per_step=5,
        )

        history = await agent.run(max_steps=max_steps)
        elapsed = time.time() - start
        final_result = history.final_result() if hasattr(history, 'final_result') else str(history)

        return {
            "success": True,
            "result": str(final_result)[:2000],
            "steps": len(history.model_actions()) if hasattr(history, 'model_actions') else 0,
            "elapsed_seconds": round(elapsed, 2),
        }
    except Exception as e:
        logger.error(f"Browser task failed: {e}")
        return {
            "success": False,
            "error": f"{type(e).__name__}: {str(e)[:500]}",
        }
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


def run_browser_task_sync(task: str, max_steps: int = 25) -> dict:
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(run_browser_task(task, llm=None, max_steps=max_steps))
        finally:
            loop.close()
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {str(e)[:500]}"}
