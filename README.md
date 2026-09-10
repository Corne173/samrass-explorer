# SAMRASS explorer: deployment instructions

Prepared on **10 September 2026** for Streamlit Community Cloud. This application explores the saved 2005–2024 SAMRASS accident records, including complete narratives, custom groups, interactive charts, and workforce comparisons. The deployment contains a fixed copy of the saved inputs; it does not run the analysis producers.

**Use a private GitHub repository and a private Streamlit app for the initial deployment.** The package contains the full accident data shown by the explorer. Repository privacy controls access to the files; Streamlit sharing settings control access to the running application.

## 1. Publish this folder with GitHub Desktop

The prepared local folder already has a Git repository on branch `main` and an initial commit. It has no remote destination. If you are using the source ZIP instead, follow the ZIP instructions near the end first.

1. Install [GitHub Desktop](https://desktop.github.com/) if needed and sign into your GitHub account.
2. Choose **File → Add local repository → Choose** and select this `samrass-explorer` folder. Select the folder containing this README, `.streamlit`, and `SAMRAS`.
3. Click **Add repository**, then **Publish repository**.
4. Use the name `samrass-explorer`, keep **Keep this code private** selected, and publish to your personal account unless the project belongs in an organisation account.
5. Wait for the upload to finish. Use **Repository → View on GitHub** to confirm the repository is marked **Private**, the branch is `main`, and the folders are present.

These steps follow GitHub's [local repository instructions](https://docs.github.com/en/desktop/adding-and-cloning-repositories/adding-a-repository-from-your-local-computer-to-github-desktop) and [publication instructions](https://docs.github.com/en/desktop/adding-and-cloning-repositories/adding-an-existing-project-to-github-using-github-desktop). You do not need to create an empty repository on the GitHub website first.

The main CSV is **61,633,584 bytes** (about 61.6 MB). GitHub Desktop can upload it through Git. The website's file-upload form has a 25 MiB limit, so use Desktop for this package. Git may display a large-file warning above 50 MiB; this file is below GitHub's 100 MiB blocking limit. [GitHub file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)

## 2. Deploy on Streamlit Community Cloud

1. Open [Streamlit Community Cloud](https://share.streamlit.io/), sign in, and connect your GitHub account. Grant the additional access needed for private repositories when prompted.
2. Choose **Create app** and the option for an app you already have in GitHub.
3. Enter the settings below. Replace `YOUR_GITHUB_NAME` with the account that owns the repository.
4. Open **Advanced settings**, select **Python 3.13**, leave secrets empty, and save.
5. Click **Deploy** and wait for installation and startup. Check the build logs if an error appears.

| Setting | Value |
| --- | --- |
| Repository | `YOUR_GITHUB_NAME/samrass-explorer` |
| Branch | `main` |
| Main file path | `SAMRAS/interactive_explorer/app.py` |
| Python version | `3.13` |
| App URL | Choose any available subdomain; `samrass-explorer` is a suggestion |
| Secrets | Leave empty; this app does not require credentials or API keys |

Use the main file path exactly, including forward slashes and letter case. Streamlit installs the requirements beside the main file and reads `.streamlit/config.toml` from the repository root. [Deployment settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [file organisation](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization), [GitHub connection](https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/connect-your-github-account)

## 3. Give colleagues access

From the Streamlit workspace, open the app's menu, then **Settings → Sharing**. Under **Who can view this app**, select **Only specific people can view this app**. Add the intended viewers' email addresses and save. Share the app's actual `https://…streamlit.app` link. Viewers authenticate using their email; they do not need Python, GitHub Desktop, or your local files.

Community Cloud currently allows one private app at a time. If your account already uses that slot, resolve that hosting choice before deploying another private app. A private repository does not prevent an app from being made public later, so check the application sharing setting as well. [Streamlit sharing](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app)

## 4. Check the hosted application

After startup, check these items in your browser:

- The dark theme and four initial charts load without an error.
- The total dataset and unfiltered reference each show **67,223** records.
- The default **Production areas** group shows **24,247** records. **Stope working face** shows **11,912**.
- Click a chart category, open **Records**, and read a complete narrative with its source identifiers.
- In **Change over time**, switch to **Displayed categories** and confirm the category lines appear.
- Open **Coverage & workforce** and check the annual workforce table and its stated denominator.
- Open the app on a narrow window or phone and verify that controls and charts remain usable.

The packaged validation results are in [VALIDATION.md](VALIDATION.md). Local validation does not establish cloud performance or capacity under several simultaneous users; the hosted check is still required.

## Using and updating the app

The sidebar sets the reference population and active group. **Groups** creates named groups or subgroups. **Explore** compares populations and supports chart selections. **Records** shows full narratives. **Coverage & workforce** explains field availability and supported exposure denominators.

Custom groups and filters are held in each user's session. A refresh, disconnect, or server restart can reset them; this version does not save group definitions. Workforce rates apply only to complete supported commodity/year populations. Accident-record percentages are not worker exposure probabilities, and narrative/assigned-cause evidence does not establish measured lighting conditions.

The hosted data are the files uploaded to this repository. Editing the original research folder does not update this copy. To update the hosted app, copy the intended revised files into this repository while preserving their paths, run the existing checks, commit in GitHub Desktop, and choose **Push origin**. Streamlit redeploys from the connected branch. It may sleep after 12 hours without traffic; an authorised viewer can wake it from the sleeping page. [Updates and hibernation](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)

## If something fails

| Symptom | Next step |
| --- | --- |
| GitHub Desktop opens the wider research repository | Remove that selection from Desktop and add the exact `samrass-explorer` folder, which has its own `.git` directory. |
| Streamlit does not list the private repository | Check the connected GitHub account, private-repository permission, and selected workspace; enter the repository manually if needed. |
| A file is missing at startup | Check both data files on GitHub and preserve the folder structure below. The cloud cannot read the local `N:` drive. |
| An import or installation fails | Check Python is `3.13` and the committed requirements file matches this package. Copy the relevant error from the Streamlit build logs for troubleshooting. |
| The app exceeds resource limits | Provide the cloud logs and the operation that triggered the error so memory use can be investigated. |
| A colleague cannot open the app | Check the viewer email under Sharing and ask them to sign in with that email. |

## Optional local commands

No local Python commands are required to publish the prepared folder through Desktop. To run or recheck it locally, open PowerShell **in this folder** and use Python 3.13:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\SAMRAS\interactive_explorer\requirements.txt
.\.venv\Scripts\python.exe -B -m unittest discover -s SAMRAS/interactive_explorer -p 'test_*.py'
.\.venv\Scripts\python.exe -m streamlit run .\SAMRAS\interactive_explorer\app.py --server.address 127.0.0.1
```

## If starting from the ZIP

The ZIP contains the application files, including the hidden configuration files, but excludes Git history and Python environments. Extract it first. In GitHub Desktop, choose **File → Add local repository** and select the extracted inner `samrass-explorer` folder. If Desktop reports that it is not a Git repository, use its **create a repository here** option. Keep the destination at that same folder; do not create a second nested folder. Leave the Git ignore and licence template choices at **None**, because `.gitignore` is already supplied and this package does not grant an open-source licence. If files remain in the Changes panel, commit them to `main`, then follow step 1 above to publish.

## Package layout

```text
samrass-explorer/
  .gitattributes
  .gitignore
  .streamlit/config.toml
  README.md
  VALIDATION.md
  SHA256SUMS.txt
  SAMRAS/
    interactive_explorer/
      app.py
      analysis.py
      charts.py
      theme.py
      requirements.txt
      test_analysis.py
      test_app.py
    samrass_analysis_outputs/
      samrass_consolidated_master.csv
      samrass_commodity_workforce_2005_2024.md
```

`SHA256SUMS.txt` records the packaged file hashes. The app, calculation code, tests, theme, and both input files are copied from the research workspace. Only the deployment copy of `requirements.txt` pins exact versions and adds the explicitly imported NumPy dependency. Source analyses, curated review files, and manuscript files are maintained in the original workspace.
