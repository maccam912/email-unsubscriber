# Email Unsubscriber

## Usage
Copy `config.toml.template` to `config.toml` and fill in the information needed. Install PDM if you don't have it (https://pdm.fming.dev/latest/) and run `pdm install`, `pdm run playwright install`, then `pdm run python main.py` to run the script. The script will first connect to the imap account specified, grab up to 100 emails in your inbox, and proceed through the following steps:

1. It will determine if the email is one you want or not. For now, this simply looks for the word "unsubscribe" in the email body.
2. If it finds this, it will extract links from the body of the email, and return the URL of the last link that says "unsubscribe" as the likely unsubscribe URL.
3. Using Langchain with gpt-3.5-turbo and the Langchain playwright tools, the language model will be instructed to navigate to the extracted URL and observe the page, perhaps click on elements, and hopefully arrive at a page confirming that you are unsubscribed.

There are lots of ways this could be improved:
- Be smarter than "does this email say the word unsubscribe" when deciding what to unsubscribe from.
- The unsubscribe links might not say the word "unsubscribe" as link text.
- The process to unsubscribe might be sending an email to request you be unsubscribed.
- The model sometimes gets stuck not knowing how to fully unsubscribe.
- Maybe archive emails after the model is confident it has unsubscribed?
- Generate reports of successful unsubscriptions?
- Extend it to handle other situations, e.g. polite responses to recruiters that you are uninterested, etc.