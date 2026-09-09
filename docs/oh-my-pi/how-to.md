# Set up Oh My Pi

Install Oh My Pi, copy the settings file, then connect your accounts. You can switch between Codex, OpenRouter, Abliteration.ai, and local Ollama models.

For the hosted providers, you'll need a ChatGPT subscription that includes Codex, an OpenRouter API key, and an Abliteration.ai API key. OpenRouter and Abliteration.ai have their own billing, separate from ChatGPT. Ollama runs models on your computer and doesn't need an API key. Set up only the providers you plan to use.

**Ask Adel for the OpenRouter and Abliteration.ai API keys unless you already have your own.**

## Quick setup with the installer

On **macOS or Linux**, open a terminal in this repository's main folder and run:

```sh
./scripts/install-omp.sh
```

To preview the steps without changing anything:

```sh
./scripts/install-omp.sh --dry
```

The installer hides key input, lets you skip providers, and asks before installing software. It leaves Ollama out entirely. For OpenRouter, choose the repository `.env` or your personal `models.yml`. Press Enter at a key prompt to skip that provider.

If you already have `models.yml`, the installer asks before replacing it. Replacement keeps only the providers you select. To keep your current setup, decline and use the manual steps below. Backups are saved privately under `~/.omp/agent/backups/`, outside the repository.

Codex still needs you to sign in through `/login openai-codex`. The script offers to open Oh My Pi for this. For optional Ollama setup, follow the manual section below.

`--dry` is a preview, not a connection test. It doesn't ask for keys, install software, write files, open Oh My Pi, or run Tasks.

After using the installer, go to **Choose a model and try it** below. For Windows or manual setup, follow the steps from the start.

## 1. Install

On **macOS or Linux**, open Terminal and run:

```sh
curl -fsSL https://omp.sh/install | sh
```

On **Windows**, open PowerShell and run:

```powershell
irm https://omp.sh/install.ps1 | iex
```

These commands download and run the official installer. Close and reopen your terminal, then check:

```sh
omp --version
```

## 2. Copy the settings file

Oh My Pi keeps your personal settings in `~/.omp/agent/`. The `~` means your home folder. On Windows, that's usually `C:\Users\YOUR_NAME`.

Open a terminal in this repository's main folder. In VS Code, open the repository, then choose **Terminal → New Terminal**.

On **macOS or Linux**, run:

```sh
mkdir -p ~/.omp/agent
cp -i docs/oh-my-pi/models.yml ~/.omp/agent/models.yml
```

If asked to overwrite an existing file, answer `n` and ask a teammate to help combine your settings.

On **Windows**, use File Explorer to create `.omp\agent` inside your home folder. Copy [models.yml](models.yml) there. If that file already exists, keep it and ask a teammate to help combine the settings.

Edit the copy in your home folder, not the file in this repository. `models.yml` connects providers. You don't need a separate `config.yml` for this setup.

## 3. Connect OpenRouter

1. Ask Adel for an OpenRouter API key, or use your own from the [OpenRouter API keys page](https://openrouter.ai/settings/keys).
2. Open `.env` in this repository's main folder. Create it if it doesn't exist.
3. Add the line below, replacing the placeholder with your key. If the line already exists, update it instead of adding another one.

```dotenv
OPENROUTER_API_KEY=PASTE_YOUR_OPENROUTER_API_KEY_HERE
```

**Start `omp` from the repository's main folder.** It reads the key from that folder's `.env`. You don't need to paste the OpenRouter key into `models.yml` or run `/login openrouter`.

If you've previously set `OPENROUTER_API_KEY` in your terminal environment, that value takes priority over `.env`.

### Alternative: put the key in models.yml

If you'd rather use OpenRouter from any folder without a repository `.env`, open your personal `~/.omp/agent/models.yml`. Under `openrouter`, replace `OPENROUTER_API_KEY` with your actual key in quotation marks:

```yaml
providers:
  openrouter:
    apiKey: "PASTE_YOUR_OPENROUTER_API_KEY_HERE"
```

This shows only the OpenRouter section. Keep the other providers and don't add a second `providers:` section. Replace the placeholder with your key, save, and restart Oh My Pi.

With this option, OpenRouter uses the key in `models.yml` instead of the one in `.env`. Keep the edited file private and outside the repository.

## 4. Connect Abliteration.ai

1. Ask Adel for an Abliteration.ai API key, or use your own from your [Abliteration.ai account](https://abliteration.ai).
2. Open your personal `~/.omp/agent/models.yml` in a text editor.
3. Replace `PASTE_YOUR_ABLITERATION_API_KEY_HERE` with your key. Keep the quotation marks and spacing. Save the file.

The file configures **Abliterated Model Large v2** (`abliterated-model-large-v2`), including its reasoning settings and model limits.

If you're using the repository `.env` option for OpenRouter, leave `OPENROUTER_API_KEY` as written in `models.yml`. It's the name of the setting in `.env`, not a placeholder.

Treat API keys like passwords. Don't commit `.env`, paste keys into chat, or share your personal `models.yml`. Only send work data to providers your team allows.

## 5. Connect Codex through your subscription

From the repository's main folder, start Oh My Pi:

```sh
omp
```

Inside Oh My Pi, type:

```text
/login openai-codex
```

Follow the sign-in link and use the ChatGPT account with your Codex subscription. If asked, select the workspace that has the subscription. Follow any remaining instructions in the terminal.

You don't need an OpenAI API key or a separate Codex CLI installation. This connection uses your subscription's Codex allowance and usage limits.

## 6. Optional: run a model locally with Ollama

1. Install [Ollama](https://ollama.com/download) for your operating system.
2. Open Ollama and leave it running.
3. In a separate terminal, download a model:

```sh
ollama pull qwen3:4b
```

The download can take a while and needs several GB of free space. Speed depends on your computer. This is a small starting model, so don't expect the same results as larger hosted models.

The supplied `models.yml` connects to Ollama at `http://127.0.0.1:11434` and discovers your installed models. No key is needed. Oh My Pi also supports automatic Ollama discovery without this entry; it's included here so you can see the settings.

If Ollama reports that it can't connect to its server, run `ollama serve` in a separate terminal and leave it open. You don't need this command if the Ollama app is already serving.

Restart Oh My Pi after downloading the model. Use `/model` and select `ollama/qwen3:4b`.

### Qwen3.8 27B Uncensored

The supplied `models.yml` also includes local model, `qwen38-27b-uncensored:latest`, with the same model limits and reasoning settings.

[Linux/Windows version](https://huggingface.co/chimingw/Qwen3.8-27B-Uncensored-OrcaRouter-GGUF)

[Apple Silicon](https://huggingface.co/chimingw/Qwen3.8-27B-Uncensored-OrcaRouter-MLX-6bit)

Once it's installed, run:

```sh
ollama list
```

Check that `qwen38-27b-uncensored:latest` (or different name) appears. Then restart Oh My Pi, open `/model`, and select `ollama/qwen38-27b-uncensored:latest`. Adding the entry to `models.yml` alone doesn't install the model.

This 27B model needs much more memory than the small `qwen3:4b` example.


The local model runs on your computer, but Oh My Pi can still use tools that access the internet.

## 7. Choose a model and try it

Inside Oh My Pi, type:

```text
/model
```

Search for `openai-codex`, `openrouter`, `abliteration`, or `ollama`. Select a model with the arrow keys and press Enter. For Abliteration.ai, choose `abliteration/abliterated-model-large-v2`.

For authorized adversarial testing, the team's recommended choices are **Daycare Blue**, **Abliteration**, or **Qwen3.8 Uncensored**. Search for Daycare Blue by name, or select one of the configured models:

- `abliteration/abliterated-model-large-v2`
- `ollama/qwen38-27b-uncensored:latest` (if you run ollama)

Try this message:

```text
Reply with one short greeting. Don't use tools or change any files.
```

Repeat with each provider you want to use. A reply confirms that connection works. API providers may charge for this request.

### Try a project skill

After the greeting works, you can check that Oh My Pi can find the project's skills. Start it from this repository's main folder and ask:

```text
Find the research-new-task, research-new-scenario, and execute-adv-task skills. Explain what each needs before it can run. Don't execute anything or contact Tyr yet.
```

These skills cover the next steps in an approved testing workflow:

- **`research-new-task`**: research and write a new Task.
- **`research-new-scenario`**: add a Scenario to an existing Task.
- **`execute-adv-task`**: run a selected Task or Scenario. The skill name is singular, not `execute-adv-tasks`.

For an actual trial, use a team-approved test environment and ask red team which Task or Scenario to use. Keep execution read-only unless real actions have been explicitly authorized. Any action that requires approval still needs a recorded human decision.

Finding the skills confirms they're available. It doesn't verify a Task run or the Tyr connection.

Restart Oh My Pi after editing `.env` or `models.yml`.

## If something doesn't work

- **`omp` isn't found:** reopen your terminal and follow any PATH instructions from the installer.
- **OpenRouter authentication fails:** check the key in the repository's `.env` and start `omp` from that same folder.
- **Abliteration.ai authentication fails:** check that you replaced the key placeholder in your home-folder copy of `models.yml`.
- **Codex asks you to sign in again:** run `/login openai-codex` again.
- **Ollama models are missing:** make sure Ollama is running, run `ollama list` to check that a model is downloaded, then restart Oh My Pi.
- **A model is missing:** check your account access and balance. For a custom configuration error, run `omp models` from the terminal and check any reported errors.
- **You hit a usage limit:** check with the red team.

## Official references

- [Oh My Pi installation](https://github.com/can1357/oh-my-pi#install)
- [Oh My Pi provider setup](https://github.com/can1357/oh-my-pi/blob/main/docs/providers.md)
- [Oh My Pi model settings](https://github.com/can1357/oh-my-pi/blob/main/docs/models.md)
- [Abliteration.ai API setup](https://abliteration.ai/docs/python)
- [Ollama download and setup](https://ollama.com/download)
- [Oh My Pi Ollama configuration](https://github.com/can1357/oh-my-pi/blob/main/docs/providers.md#built-in-local-engines)
