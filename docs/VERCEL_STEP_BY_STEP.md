# Vercel deployment – step by step (no experience needed)

This guide assumes you have never used Vercel. Do the steps in order. Each step tells you exactly where to click and what to type.

---

## What is Vercel?

Vercel is a service that **runs your bot on the internet**. Right now your bot code lives on your computer and on GitHub. For Telegram to call your bot when someone sends a message, the code must run on a **server on the internet**. Vercel provides that server. You give Vercel your GitHub repo; it copies the code, runs it, and gives you a URL (like `https://something.vercel.app`). You then tell Telegram: “When someone messages my bot, call this URL.” That’s deployment.

---

## Part 1: Make sure GitHub has the latest code

**What we’re doing:** Your computer might have newer files than GitHub. We want GitHub to have the same files as your computer (including the fixed `vercel.json`).

1. On your computer, open **Cursor** (or your code editor) and open the project folder: `margai-ghost-tutor-pilot` (or the folder that contains `vercel.json`, `api`, `lib`, etc.).

2. Open **Terminal** (in Cursor: Terminal → New Terminal, or the tab at the bottom).

3. In the terminal, go to the project folder. Type this and press Enter (use your actual path if different):
   ```bash
   cd /Users/rajeshmukherjee/Desktop/04_Data_Science/Projects/Cursor_test_project/margai-ghost-tutor-pilot
   ```

4. See if Git has any changes that aren’t on GitHub yet. Type and press Enter:
   ```bash
   git status
   ```
   - If it says “nothing to commit, working tree clean” and “Your branch is up to date with 'origin/main'”, your latest code is already on GitHub. **Skip to Part 2.**
   - If it lists modified files (e.g. `vercel.json`) or says “Your branch is ahead of 'origin/main'”, continue below.

5. Add all changed files and send them to GitHub:
   ```bash
   git add .
   git commit -m "Update vercel config for deployment"
   git push origin main
   ```
   - If it asks for your GitHub username/password or a token, enter them. If you use two-factor auth, you may need a **Personal Access Token** from GitHub instead of a password.
   - Wait until it says something like “Successfully pushed” or shows no errors.

6. In your browser, open GitHub: **https://github.com/Pandauser2/margai-ghost-tutor**
   - Open the file **vercel.json**.
   - Check that inside it you see **`"api/*.py"`** (with a single star `*`), not `"api/**/*.py"` (two stars). If it’s `api/*.py`, GitHub is up to date. If not, go back to step 5 and push again.

---

## Part 2: Log in to Vercel and open your project

**What we’re doing:** Opening the Vercel website and your project so we can trigger a new deployment.

1. In your browser, go to: **https://vercel.com**

2. **Log in** (or sign up if you don’t have an account).
   - Use “Continue with GitHub” if possible so Vercel can see your repos.

3. On the Vercel home page you’ll see a list of projects. Find **margai-ghost-tutor-pilot** (or the name you gave this bot project).
   - Click the **project name** (one click). That opens the project.

4. You should now see the **project page**, with tabs like “Deployments”, “Settings”, “Analytics”, etc. Remember this page; we’ll use it in the next part.

---

## Part 3: Start a new deployment from the latest GitHub code

**What we’re doing:** Telling Vercel to copy the **latest** code from GitHub and build it again. That way the old `vercel.json` is replaced by the one on GitHub.

1. On the project page, click the **“Deployments”** tab at the top (if you’re not already there).

2. At the top of the deployments list you’ll see something like “Create Deployment” or a button that says **“Redeploy”** or **“Deploy”**.  
   - If you see **“Create Deployment”**: click it. Then choose branch **main** and click **Deploy**.  
   - If you don’t see that: go to step 3.

3. **Alternative – Redeploy the latest deployment:**
   - In the list of deployments, the **first row** is usually the latest. Click that **first row** (the deployment at the top).
   - A new page opens for that deployment. Near the top you’ll see a button with three dots **⋮** or “Redeploy”.
   - Click **⋮** (or “Redeploy”).
   - Click **“Redeploy”** in the menu.
   - A small window may ask “Use existing Build Cache?” or similar. **Uncheck** that box (so Vercel does a fresh build from GitHub).
   - Click the button that confirms redeploy (e.g. **“Redeploy”** again).

4. Wait 1–2 minutes. The deployment status will change from “Building” to “Ready” (or “Error” if something failed).
   - If it says **Ready**: your latest code from GitHub is now live. **Go to Part 4** to get your bot URL and set the Telegram webhook.
   - If it says **Error**: click that deployment, open the **“Build Logs”** or **“Logs”** section, and copy the error message. You can use that to ask for help or search the error online.

---

## Part 4: Get your bot URL and set the Telegram webhook

**What we’re doing:** Finding the URL where your bot is running and telling Telegram to use it.

1. On the **same deployment** that shows **Ready**, look for **“Domains”** or a URL like:
   **`https://margai-ghost-tutor-pilot-xxxxx.vercel.app`**
   - Click that URL or copy it. This is your **bot URL**. The part that matters for Telegram is:  
     **`https://margai-ghost-tutor-pilot-xxxxx.vercel.app/api/telegram_webhook`**  
     (same URL + `/api/telegram_webhook` at the end).

2. Open **Telegram** (on your phone or desktop) and get your **bot token** from BotFather if you don’t have it saved:
   - Search for **@BotFather** in Telegram.
   - Send **/mybots** → choose your bot → **API Token**. Copy the token (looks like `123456789:ABCdef...`).

3. On your **computer**, open **Terminal** again. Replace the two placeholders and run **one** of these (all on one line):

   **If you don’t use a secret token:**
   ```bash
   curl -X POST "https://api.telegram.org/botPUT_YOUR_BOT_TOKEN_HERE/setWebhook?url=https://PUT_YOUR_VERCEL_URL_HERE/api/telegram_webhook"
   ```
   Example (fake token and URL):
   ```bash
   curl -X POST "https://api.telegram.org/bot7123456789:AAHxxx/setWebhook?url=https://margai-ghost-tutor-pilot-r1ses4j7n.vercel.app/api/telegram_webhook"
   ```

   - Replace **PUT_YOUR_BOT_TOKEN_HERE** with the token from BotFather (no spaces).
   - Replace **PUT_YOUR_VERCEL_URL_HERE** with your real Vercel URL (e.g. `margai-ghost-tutor-pilot-r1ses4j7n.vercel.app`), **without** `https://` in the middle of the URL (the command already has `https://` before it).
   - Press Enter.

4. The answer should look like: **`{"ok":true,...}`**
   - If you see **`"ok":true`**: the webhook is set. Open your bot in Telegram and send a message to test.
   - If you see **`"ok":false`** or an error: check that the token and URL are correct (no extra spaces, full URL with `/api/telegram_webhook`).

---

## Part 5: If something goes wrong

- **“Build Failed” on Vercel**  
  Click the failed deployment → open **Build Logs**. If the error says “pattern doesn’t match”, GitHub might still have the old `vercel.json`. Do **Part 1** again (push `vercel.json` with `api/*.py`), then **Part 3** again (redeploy).

- **Telegram doesn’t reply**  
  Make sure you set the webhook (Part 4) **after** the deployment is **Ready**. Check that in Vercel → **Settings** → **Environment Variables** you added all the required variables (e.g. `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `PINECONE_API_KEY`, etc.).

- **Vercel says “not getting latest from GitHub”**  
  That usually means the deployment was built from an old commit. Do **Part 3** and use **Redeploy** with **Build Cache** turned off, or **Create Deployment** from branch **main**.

---

## Quick checklist

- [ ] Pushed latest code to GitHub (`git add .` → `git commit` → `git push origin main`).
- [ ] On GitHub, `vercel.json` contains **`api/*.py`**.
- [ ] Logged in to Vercel and opened project **margai-ghost-tutor-pilot**.
- [ ] Started a new deployment (Create Deployment from **main**, or Redeploy latest with cache off).
- [ ] Deployment status is **Ready**.
- [ ] Copied the Vercel URL and called Telegram’s setWebhook with:  
      `url=https://YOUR_VERCEL_URL/api/telegram_webhook`.
- [ ] Environment variables are set in Vercel (Settings → Environment Variables) for Production (and Preview if you use it).

When all are done, your bot should respond in Telegram using the latest code from GitHub.
