from langchain_openai import ChatOpenAI

class BaseModel:
    '''
    Template for our LLM base, currently using GPT 4o just because it's cheap
    '''
    def __init__(self, model_name="gpt-4o-mini", temperature=0.7):
        self.model_name = model_name
        self.temperature = temperature
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature
        )

    def getModel(self):
        return self.llm
