# YouTube upload setup

One-time Google Cloud setup so Snapify Editor can upload/schedule Shorts on your behalf.

## 1. Create a Google Cloud project
- Go to [console.cloud.google.com](https://console.cloud.google.com/)
- Create a new project (or pick an existing one)

## 2. Enable the YouTube Data API v3
- In the project, go to **APIs & Services → Library**
- Search "YouTube Data API v3" → **Enable**

## 3. Configure the OAuth consent screen
- **APIs & Services → OAuth consent screen**
- User type: **External** (unless you have a Google Workspace org)
- Fill in app name, your email, developer contact
- Scopes: add `.../auth/youtube.upload` and `.../auth/youtube.readonly`
- Test users: add the Google account(s) that own the YouTube channel(s) you'll upload to (required while the app is in "Testing" mode)

## 4. Create an OAuth client ID
- **APIs & Services → Credentials → Create Credentials → OAuth client ID**
- Application type: **Web application**
- Authorized redirect URIs: add exactly
  ```
  http://localhost:5000/youtube/oauth2callback
  ```
  (match `YOUTUBE_REDIRECT_URI` in your `.env` if you changed the port/host)
- Click **Create**, then **Download JSON**

## 5. Install the credentials file
- Save the downloaded file as `client_secret.json` in the project root (same folder as `app.py`)
- Confirm `.env` has:
  ```
  YOUTUBE_CLIENT_SECRETS_FILE=client_secret.json
  YOUTUBE_TOKEN_FILE=youtube_token.json
  YOUTUBE_REDIRECT_URI=http://localhost:5000/youtube/oauth2callback
  ```

## 6. Authorize
- Start the app (`python3 app.py`)
- Visit `http://localhost:5000/youtube/authorize`
- Sign in with the Google account for the channel you want to upload to, accept the consent screen
- You'll see "YouTube connected successfully" — a `youtube_token.json` is now saved in the project root and reused (and auto-refreshed) for future uploads

## Notes
- While the OAuth consent screen is in **Testing** mode, only accounts listed as test users can authorize. Publish the consent screen (Google review required) to allow any account.
- `client_secret.json` and `youtube_token.json` are both secrets — never commit them (already covered by `.gitignore`).
- If you rotate/delete the OAuth client in Google Cloud, delete `youtube_token.json` and re-run step 6.
- Uploaded videos default to `privacyStatus: private`. Change this per-upload in the Publish modal, or it's forced to `private` automatically whenever you schedule a future `publishAt` (YouTube then flips it public at that time).
