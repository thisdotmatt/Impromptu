# graph_skeleton.py
from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, START, END
from models.BaseModel import BaseModel
from config import SPEC_GENERATION_PROMPT, USE_MOCK_LLM
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from utils.usage import UsageTracker
from openai import RateLimitError, OpenAIError

# state that gets passed to each agent
# feel free to use "memory" as a way of passing context
class GraphState(TypedDict, total=False):
    user_input: str
    spec: Dict[str, Any]
    usage: Dict[str, Any]
    memory: Dict[str, Any]
    usage_tracker: UsageTracker # this tracks tokens and cost for us

def inputHandler(state: GraphState) -> GraphState:
    state.setdefault("memory", {})
    state.setdefault("usage", {"nodes": {}})
    if not state.get("user_input"):
        raise ValueError("GraphState missing 'user_input'")
    state["usage_tracker"] = UsageTracker()
    return state

# use this for mocking the specification agent 
def _mockSpec(user_prompt: str) -> dict:
    return {
        "goal": f"Interpret user request: {user_prompt}",
        "inputs": ["5V supply", "1x pushbutton (optional)"],
        "outputs": ["1x LED blinking at ~1 Hz"],
        "constraints": {"max_current_mA": 10, "breadboard_layout": True},
        "notes": ["This is MOCK mode output", "Replace with real LLM later"]
    }

# generates a formal specification based on direct user input
def specGeneration(state: GraphState) -> GraphState:
    user_prompt = state["user_input"]
    tracker = state["usage_tracker"]

    if USE_MOCK_LLM:
        state["spec"] = _mockSpec(user_prompt)
        tracker.zeroNode("spec_generation")
        state["usage"]["nodes"]["spec_generation"] = tracker.nodeReport("spec_generation")
        return state

    llm = BaseModel().getModel()
    prompt = PromptTemplate(template=SPEC_GENERATION_PROMPT, input_variables=["user_prompt"])
    parser = JsonOutputParser()
    chain = prompt | llm | parser

    # allows us to catch any openai errors
    try:
        with tracker.node("spec_generation", provider="openai"):
            spec = chain.invoke({"user_prompt": user_prompt}) # calls our model with the specified prompt
        state["spec"] = spec
    except RateLimitError as e:
        state["spec"] = {"error": "OpenAI quota exceeded"}
        tracker.zeroNode("spec_generation")
        state["usage"]["nodes"]["spec_generation"] = tracker.nodeReport("spec_generation")
        print("RateLimitError:", e)
        return state
    except OpenAIError as e:
        state["spec"] = {"error": str(e)}
        tracker.zeroNode("spec_generation")
        state["usage"]["nodes"]["spec_generation"] = tracker.nodeReport("spec_generation")
        print("OpenAI API Error:", e)
        return state
    
    # generate a per-agent report
    state["usage"]["nodes"]["spec_generation"] = tracker.nodeReport("spec_generation")
    return state

def returnNode(state: GraphState) -> GraphState:
    tracker = state["usage_tracker"]
    state["usage"]["totals"] = tracker.totalReport()
    return state

# add your agents here
def buildGraph():
    graph = StateGraph(GraphState)
    graph.add_node("input_handler", inputHandler)
    graph.add_node("spec_generation", specGeneration)
    graph.add_node("return_node", returnNode)
    graph.add_edge(START, "input_handler")
    graph.add_edge("input_handler", "spec_generation")
    graph.add_edge("spec_generation", "return_node")
    graph.add_edge("return_node", END)
    return graph.compile()

if __name__ == "__main__":
    graph = buildGraph()
    res = graph.invoke({"user_input": "Design a circuit that blinks an LED every second"})
    print(res["spec"])
    print(res["usage"])
