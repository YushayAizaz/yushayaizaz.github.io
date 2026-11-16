# Set up and deploy the author platform

The free path uses a private GitHub repository, GitHub Actions on the included runner allowance, the hosted Pages CMS editor, and Cloudflare Pages on its free plan. Use the free `pages.dev` address. Vercel Hobby is an alternative for eligible personal, non-commercial use. Plan limits and eligibility can change. [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/) · [Vercel Hobby fair use](https://vercel.com/docs/limits/fair-use-guidelines)

You need Git, Node 24 LTS, Python 3.12 or newer, and access to the GitHub and Meta accounts that will own the site. On Windows, use Git Bash for the shell blocks below. The reader and CMS work independently of Instagram credentials.

## Step 1 — Push the project to GitHub

1. Extract the ZIP. Open a terminal in the `yushay-author-platform` folder that contains `package.json`, `.pages.yml`, and `.github/workflows/`.
2. Sign in to GitHub and open [New repository](https://github.com/new). Choose your personal account and a name such as `yushay-author-platform`. Select **Private** to keep draft Markdown and Git history private. Leave the README, license, and gitignore initialization options off. Click **Create repository**.
3. Copy the HTTPS repository URL shown under Quick setup. Initialize and push from the extracted folder, replacing the URL in the last two lines as appropriate.

   ```bash
   git init -b main
   git add .
   git status --short
   git commit -m "Set up the author platform"
   git remote add origin https://github.com/YOUR-GITHUB-USERNAME/yushay-author-platform.git
   git push -u origin main
   ```

   Check the staged files before committing. `.pages.yml` and the workflows belong in Git. Local `.env`, tokens, and build output stay out of Git. Authenticate through Git Credential Manager, GitHub CLI, or SSH if prompted. If you already have a remote with editorial commits, clone it and apply the new code on a branch so you can review the diff while preserving existing content.

4. Refresh the GitHub repository and confirm that `main` contains `src/`, `public/`, and the workflows. In **Settings → Actions → General**, ensure your account permits the repository's workflows and that branch rules allow the import workflow to push to the default branch. Its job explicitly requests `contents: write`. Use GitHub **Billing and licensing → Budgets and alerts** to check your included Actions usage and set any spending limit to stop billed overages. The included allowance is shared with your other repositories. [GitHub push guide](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github) · [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

## Step 2 — Connect Instagram imports

### Production: Behold JSON feed

The live repository uses the bundled `@yushayaizaz` Behold JSON feed. Neither `INSTAGRAM_ACCESS_TOKEN` nor `INSTAGRAM_USER_ID` is required. To point it at another Behold feed, set `BEHOLD_FEED_URL` under **Settings → Secrets and variables → Actions → Variables**. Set the same variable in your shell to override it locally.

Run **Actions → Import Instagram dispatches → Run workflow** for a manual check. Scheduled runs check every hour at minute 0 UTC. Behold Free refreshes the feed once a day. A run with no new posts makes no commit, and a successful push of new entries triggers the Pages deployment. Keep an eye on [Behold’s monthly view limit](https://behold.so/pricing/).

### Optional local use: Meta app with Instagram Login

1. On Instagram, confirm `@yushayaizaz` is a **public professional Creator** account. If switching from a personal account, open the profile menu, go to **Settings and activity → Account type and tools → Switch to professional account**, and select **Creator** when asked to choose the account type.
2. Sign in at [Meta for Developers → My Apps](https://developers.facebook.com/apps/). Complete developer registration if prompted. Click **Create App**. Supply an app name, such as `Yushay Editorial Import`, and your contact email when prompted. If your app wizard lists **Manage messaging and content on Instagram**, choose it and complete the wizard. If it shows the product-based setup, choose **Other → Next → Business → Next**, complete the app details and business selection shown, then select **Create app**. In the resulting dashboard, under **Add products to your app**, find **Instagram → Set up**. [Meta Instagram app setup](https://developers.facebook.com/docs/instagram-platform/create-an-instagram-app/)
3. Open **Instagram → API setup with Instagram login**. In the use-case dashboard, you may reach this under **Use cases → Manage messaging and content on Instagram → Customize**. Use the Instagram Login version. It works with a professional account without a linked Facebook Page. The importer reads media and requires `instagram_business_basic`. Local imports use polling. The website itself does not need a Meta webhook, callback server, or public OAuth sign-in. [Meta Instagram Login permissions](https://www.postman.com/meta/instagram/folder/1z5vxzu/instagram-api-with-instagram-login)
4. In **Generate access tokens**, click **Add account**, sign in as `@yushayaizaz`, and approve access. If Meta requires a tester invitation first, go to **App roles → Roles → Add People → Instagram Tester**, enter `yushayaizaz`, and send the invitation. On Instagram as that account, open [Apps and websites → Tester invites](https://www.instagram.com/accounts/manage_access/) and accept it. Return to the app dashboard and retry **Add account**. This setup is for the account you own or manage and add to the app under Standard Access. Accessing other creators' accounts requires a different review and authorization flow. [Meta access levels](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/)
5. Next to the account in **Generate access tokens**, click **Generate token** and confirm the prompt. Copy the Instagram user access token into a private password manager. Copy the numeric **Instagram account/user ID** on the same account row. Use that ID as `INSTAGRAM_USER_ID`. The Instagram app ID, Facebook Page ID and handle are different identifiers.

### Confirm token duration and account ID

If the dashboard gives you a long-lived Instagram user token, that is the value to store. If Meta supplies a short-lived Instagram user token, exchange it while it is valid. Under **API setup with Instagram login**, find and reveal the **Instagram app secret** for this app when needed. Run the exchange locally in a private terminal. The result includes `access_token` and `expires_in` in seconds. A long-lived result is valid for about 60 days. Keep the app secret out of GitHub, the CMS, and the hosting dashboard. [Meta long-lived token exchange](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/#long-lived)

```bash
read -r -s -p 'Instagram app secret: ' ig_secret; printf '\n'
read -r -s -p 'Short-lived Instagram user token: ' ig_token; printf '\n'
printf 'data-urlencode = "client_secret=%s"\ndata-urlencode = "access_token=%s"\n' "$ig_secret" "$ig_token" |
  curl -q --config - --fail --silent --show-error --get \
    --data-urlencode 'grant_type=ig_exchange_token' https://graph.instagram.com/access_token
printf '\n'
unset ig_secret ig_token
```

If the account row does not show the ID, use the Instagram Login profile endpoint with your token. The command hides input and passes the authorization header through standard input. Use the `user_id` field for the importer and confirm that `username` is `yushayaizaz`. If you configured a different supported API version, use it in the command and in the repository variable.

```bash
read -r -s -p 'Instagram user token: ' ig_token; printf '\n'
printf 'Authorization: Bearer %s\n' "$ig_token" |
  curl -q --fail --silent --show-error --header @- \
    'https://graph.instagram.com/v27.0/me?fields=user_id,username'
printf '\n'
unset ig_token
```

### Run the importer locally with a Meta token

Store the access token in a private password manager. Set these environment variables only if using the optional local Graph API mode. Install the Python dependencies with `python -m pip install -r requirements.txt` and run the following from the repository root.

```bash
read -r -s -p 'Long-lived Instagram user token: ' INSTAGRAM_ACCESS_TOKEN; printf '\n'
read -r -p 'Numeric Instagram user ID: ' INSTAGRAM_USER_ID
export INSTAGRAM_ACCESS_TOKEN INSTAGRAM_USER_ID
python scripts/sync_instagram.py --dry-run
unset INSTAGRAM_ACCESS_TOKEN INSTAGRAM_USER_ID
```

A run with no token uses Behold. To hold new posts for editorial review, set the repository variable `INSTAGRAM_IMPORT_DRAFT` to `true`. This keeps the articles out of the published edition, but their assets in `public/` are still included in a static deployment.

### Refresh the token before it expires

Put a recurring reminder at about day 45 after issuance or renewal. Meta allows a valid long-lived token to be refreshed after it is at least 24 hours old, with `instagram_business_basic` still granted. Use the current token from your private password manager. The refresh can extend validity by 60 days and returns the credential to store.

```bash
read -r -s -p 'Current long-lived Instagram token: ' ig_token; printf '\n'
printf '%s' "$ig_token" |
  curl -q --fail --silent --show-error --get \
    --data-urlencode 'grant_type=ig_refresh_token' \
    --data-urlencode 'access_token@-' https://graph.instagram.com/refresh_access_token
printf '\n'
unset ig_token
```

Use the returned `access_token` for future local runs. Update your private copy and record the new expiry from `expires_in`. The numeric ID stays the same for the same account and app. Run the dry-run check after updating. If a token already expired or was revoked, repeat **Generate token** and store a fresh one. [Meta refresh requirements](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/#long-lived)

## Step 3 — Edit through Pages CMS

1. Open [Pages CMS](https://app.pagescms.org/) and choose **Sign in with GitHub**. Authorize the login and install the Pages CMS GitHub app on the account that owns the repository. Choose **Only select repositories** if offered and grant access to the author platform repository.
2. Open your repository and choose the default branch, normally `main`. The bundled `.pages.yml` loads the collections and media manager. If the app offers to create a new configuration, confirm you've selected the repository and branch that contain the existing file before proceeding.
3. Select a collection and open an entry or create a new one. Add a title, date, required metadata, and text in the rich-text editor. Save while **Draft** is on to hold an entry. To publish, turn **Draft** off, which writes `draft: false`, then save. Each save writes a Git commit. Once Step 4 is connected, normal CMS commits trigger the hosting provider's Git integration.

   | Collection | What to edit |
   | --- | --- |
   | The Evening Dispatches | Write a new field note with a unique positive dispatch number, or expand an imported dispatch. Preserve its Instagram identity and stored image paths. |
   | Original Works | Choose an essay, poem, short story, or reflection and enter a reading time. Use blank lines between poem stanzas. |
   | The Book · Overview & Excerpts | Maintain one overview. Add entries of kind `excerpt` and enter Chapter number and Order. An overview can hold the status, progress, and themes. |
   | Events & Recognition | Choose a type such as upcoming gathering, appearance, award, publication, or milestone. Add the confirmed date, location, organization, summary, optional photographs with alt text, and the full notes in the body. |

4. For event listings saved with a date only, the project reads that value as midnight UTC and displays dates in Budapest time. For an upcoming event that should stay upcoming until its start time, enter a full offset-bearing timestamp through Markdown, for example `2030-05-18T19:00:00+02:00`. The ledger is dated at build time. A subsequent build moves elapsed gatherings into the appearances archive.
5. To add the press portrait, export an approved JPEG named `yushay-aizaz-portrait.jpg`. In Pages CMS, open **Media → Editorial images → uploads** and upload it there, or add it directly to `public/images/uploads/` and commit. Confirm that the exact case-sensitive filename appears in GitHub. After the next build, `/achievements/#press-kit` shows the portrait and download link. Ask the photographer to approve sharing and remove private location metadata if needed. [Pages CMS quick start](https://pagescms.org/docs/quick-start/)

## Step 4 — Host the site and request builds after bot commits

Pick one host. Both use the project root, Node 24 LTS, build command `npm run build`, and output directory `dist`. The site is static. Hosting needs no Instagram tokens or Meta app secret.

### Cloudflare Pages Free

1. Sign in to [Cloudflare](https://dash.cloudflare.com/). Open **Workers & Pages → Create application → Pages → Connect to Git**. Choose GitHub, authorize the Cloudflare GitHub app for the repository, select the repository, and begin setup.
2. Choose a project name and the repository's default branch for production. Select the **Astro** preset or enter the build settings above. Keep the root at the repository root. Set the build environment variable `NODE_VERSION` to `24` if needed. The repo also includes `.nvmrc` with the same major version.
3. Choose **Save and Deploy**. Open the resulting HTTPS `pages.dev` address. In the Pages project settings, set `SITE_URL` to that exact HTTPS origin without a path, then redeploy once so the build emits canonical URLs. [Cloudflare Git integration](https://developers.cloudflare.com/pages/get-started/git-integration/) · [Build configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/) · [Node version settings](https://developers.cloudflare.com/pages/configuration/build-image/)

### Vercel Hobby for eligible personal, non-commercial use

1. Sign in to [Vercel](https://vercel.com/) with GitHub. Under your personal Hobby account, choose **Add New → Project**, then import the GitHub repository. Grant Git integration access if prompted.
2. Choose the **Astro** preset and confirm the root, build command and output directory above. Verify **Settings → Build and Deployment → Node.js Version** is **24.x**. Use the repository's default branch as the production branch. Deploy and open the assigned HTTPS `vercel.app` address.
3. Add `SITE_URL` with that HTTPS origin under **Settings → Environment Variables** for Production and redeploy once. If Vercel declines a deployment because of commit author or access restrictions, inspect the GitHub commit check and the Vercel deployment log. For a site promoting paid services or other commercial work, use the Cloudflare Pages free path within its plan limits instead. [Vercel project setup](https://vercel.com/docs/projects/managing-projects) · [Astro on Vercel](https://vercel.com/docs/frameworks/frontend/astro) · [Vercel fair use](https://vercel.com/docs/limits/fair-use-guidelines)

### Configure the optional import deploy hook

The imported content is pushed with GitHub's `GITHUB_TOKEN`. That push does not start a second push-based GitHub Actions run. A host's Git integration may already build the commit. The hook is an explicit build request for the bot path when needed.

1. For **Cloudflare Pages**, open **Workers & Pages → your Pages project → Settings → Builds → Add deploy hook**. For **Vercel**, open **your project → Settings → Git → Deploy Hooks**.
2. Name the hook `Instagram import`, select the **default production branch** (usually `main`), create the hook, and copy its HTTPS URL.
3. In GitHub, go to **Settings → Secrets and variables → Actions → Secrets → New repository secret**. Name it `DEPLOY_WEBHOOK_URL` and paste the complete URL. The hook URL grants deployment access. Keep it private and replace it if exposed.
4. The included `.github/workflows/instagram-sync.yml` uses a separate step after a successful `git push`. It reads the secret through an environment variable and sends an HTTPS `curl -X POST "$DEPLOY_WEBHOOK_URL"` request. A missing secret skips the POST. A run with no new commit or a failed push does not reach the deployment step. An accepted request queues the provider build. It becomes live once the provider finishes successfully.
5. Run the workflow when there is a new eligible Instagram post. Check the new Git commit, the hook step, and the provider dashboard's production deploy for that commit. Open `/dispatches/` after the provider reports success. If an import was stored as a draft, publish it through the CMS first. If the hook fails after the push, the commit is already in GitHub. Fix or recreate the hook and retrigger the current production branch from the host dashboard, or run the provider's hook locally. Rerunning an unchanged import will skip the hook. If both Git integration and the hook produce duplicate builds for bot commits, remove the optional secret once you have verified the Git integration consistently handles them. [GitHub token behavior](https://docs.github.com/en/actions/concepts/security/github_token) · [Cloudflare deploy hooks](https://developers.cloudflare.com/pages/configuration/deploy-hooks/) · [Vercel deploy hooks](https://vercel.com/docs/deploy-hooks)

### Deployment checks

- Open `/`, `/dispatches/`, `/works/`, `/book/`, and `/achievements/#press-kit` on the deployed origin. Check that neither the private working-edition banner nor the demonstration drafts appear.
- Use one of the public press-kit copy buttons on HTTPS and paste the result into a local text editor. When a portrait is present, test the download. The contact link opens `@yushayaizaz` on Instagram, where visitors can select **Message**.
- Make a small approved edit in Pages CMS. Confirm the branch receives the commit and the host deploys it. If the host blocks or queues a build, look at the provider log and its free plan usage rather than repeatedly pressing deploy.
- Check the most recent Actions run and Behold usage periodically. Renew the Meta token before expiry only if you use the optional local Instagram Login mode.

## GitHub Pages root launch

The launch workflow targets the public user-site repository `YushayAizaz/yushayaizaz.github.io` on `main`. It publishes only the built `dist/` folder and uses `https://yushayaizaz.github.io` as its origin. The public repository also exposes the files committed to it. Keep private writing and credentials out of that repository.

If the repository has not been created, use Git and the authenticated GitHub CLI from the extracted project folder. First run `gh auth login --hostname github.com --web --git-protocol https` and confirm the correct account with `gh api user --jq .login`. These commands assume a fresh extraction and an unused repository name.

```bash
git init -b main
git add .
git status --short
git commit -m "Launch Yushay Aizaz author platform"
gh repo create YushayAizaz/yushayaizaz.github.io --public --source=. --remote=origin --push
gh api --method POST repos/YushayAizaz/yushayaizaz.github.io/pages -f build_type=workflow
gh workflow run deploy-pages.yml --repo YushayAizaz/yushayaizaz.github.io --ref main
```

If you already created the empty repository, set it as `origin` and run `git push -u origin main` in place of `gh repo create`. If Pages already exists, set **Settings → Pages → Build and deployment → Source** to **GitHub Actions** in place of the POST. Watch the deployment in **Actions → Deploy author platform to GitHub Pages**. [GitHub Pages publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) · [Pages API](https://docs.github.com/en/rest/pages/pages#create-a-github-pages-site)

Ordinary pushes to `main` deploy automatically. After an Instagram import successfully pushes new content to this user-site repository, the sync workflow explicitly dispatches the Pages workflow. GitHub allows workflow-dispatch events from `GITHUB_TOKEN`. The optional `DEPLOY_WEBHOOK_URL` remains available for repositories hosted on the other providers. [GitHub token trigger behavior](https://docs.github.com/en/actions/concepts/security/github_token)
