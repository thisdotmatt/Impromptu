# Impromptu
Impromptu is an automatic circuit prototyper that turns natural language prompts into working breadboard circuits. It combines AI-driven circuit design with a custom pick-and-place machine, making circuit building easy for everyone.

## 📑 Table of Contents

- [Getting Started](#-getting-started)
- [Documentation](#-documentation)
- [Contributing](#-contributing)

## 🚀 Getting Started

1. Clone this repository in a terminal of your choice:
```
git clone https://github.com/thisdotmatt/Impromptu.git
cd Impromptu
```
2. Download the dependencies. Our repository uses **uv**, a fast package manager which you can download [here](https://github.com/astral-sh/uv). Then, run:
```
uv python install
uv sync
```

3. Add your OpenAI key to your environment variables: 
```
export OPENAI_API_KEY="<YOUR_OPENAI_KEY_HERE>"   // macOS/Linux
setx OPENAI_API_KEY "<YOUR_OPENAI_KEY_HERE>"     // Windows only
```

Make sure to restart your IDE after doing this. You can verify this has worked by executing `uv run src/utils/check_api_key.py` in your terminal. The result should be your API key in the form "sk..."

4. That's it! To run the core circuit design loop, run:
```
cd src
uv run main.py
```

## 📚 Documentation

You can find the relevant documentation [here](docs/docs.md).

## 🤝 Contributing

Contributions are welcome - to add a feature, create a new branch or fork this repository, and then file a pull request once your feature is complete.
