from abc import ABC as AbstractBaseClass
from abc import abstractmethod


class BaseModel(AbstractBaseClass):
    """
    Abstract base class for LLM models.
    """

    def __init__(self, model_name, temperature):
        self.model_name = model_name
        self.temperature = temperature

    @abstractmethod
    def getModel(self):
        """
        Should return a BaseChatModel that you can call like so:

        ```python
        model = DerivedModel(model_name, temperature)
        llm = model.getModel()
        llm.invoke()
        ```
        """
        pass
