# Impromptu
Impromptu is an automatic circuit prototyper that turns natural language prompts into working breadboard circuits. It combines AI-driven circuit design with a custom pick-and-place machine, making circuit building easy for everyone.

https://github.com/user-attachments/assets/af829149-51b6-4d58-9f37-0a1cd9a2d0af

## 📑 Table of Contents

- [Getting Started](#-getting-started)
- [Documentation](#-documentation)
- [Contributing](#-contributing)

## 🚀 Getting Started

1. Clone this repository in a terminal of your choice:

```bash
git clone https://github.com/thisdotmatt/Impromptu.git
cd Impromptu
```

2. Download the dependencies. Our repository uses **uv**, a fast package manager which you can download [here](https://github.com/astral-sh/uv). Then, run:

```bash
uv python install
uv sync
```

If you plan to use our web app as opposed to just the terminal version of Impromptu, you'll need to have [node/npm](https://nodejs.org/en/download/) installed. Once installed, run `npm install` to download all required dependencies.

3. Configure your Impromptu environment.

Add your OpenAI key to your environment variables:

```bash
export OPENAI_API_KEY="<YOUR_OPENAI_KEY_HERE>"   // macOS/Linux
setx OPENAI_API_KEY "<YOUR_OPENAI_KEY_HERE>"     // Windows only
```

Make sure to restart your IDE after doing this. You can verify this has worked by executing `uv run src/utils/check_api_key.py` in your terminal. The result should be your API key in the form "sk..."

You'll also want to turn off USE_MOCK_LLM, which allows developers to test the system without using API credits (mocks the output of each workflow). You can find the configeration in [config.py](./src/backend/config.py).

4. Our circuit generation script requires LTSpice to be installed - place the path of the LTSpice executable in the config file.

5. That's it! From here, you have two ways of running Impromptu - terminal-based and web-based. To run the terminal application:

```bash
cd src/backend
uv run executor.py
```

To run the web application, you'll need to first start our API locally:

```bash
cd src/backend
uv run uvicorn server:app --reload
```

Then, start the web app with:

```bash
cd src/frontend
npm run dev
```


This will start your webapp at `http://localhost:3000/`.

## 📚 Documentation

You can find the relevant documentation [here](docs/docs.md).

## 🤝 Contributing

Contributions are welcome - to add a feature, create a new branch or fork this repository, and then file a pull request once your feature is complete.

Testing the local API can be done via terminal with the command:

```bash
curl --no-buffer -X POST -H "Content-Type: application/json" -d "{\"userInput\":\"Blink an LED\",\"conversationContext\":\"some prior messages\",\"selectedModel\":\"gpt-4\",\"retryFromStage\":\"spec_generation\"}" http://127.0.0.1:8000/create/test-run
```
