# Deploying the Load Balancer

This project has two parts: GitHub Pages serves the static browser interface, and Render runs the Python API and load-balancer processes.

## 1. Deploy the backend on Render

1. In Render, create a Blueprint from this repository and select the `codex/deploy-github-pages-render` branch for review, or merge this setup into `main` first.
2. Render reads `render.yaml` and creates the `load-balancer-api` web service.
3. Set `CONTROL_TOKEN` to a strong, URL-safe value using letters, numbers, hyphens, and underscores. The control panel asks for this token and keeps it in the browser session.
4. After the service is live, copy its HTTPS URL, such as `https://load-balancer-api.onrender.com`.

The free Render plan may spin down the service after inactivity, so the first request after a quiet period can take longer.

## 2. Configure and deploy GitHub Pages

1. In the repository, open **Settings → Pages** and choose **GitHub Actions** as the build and deployment source.
2. Open **Settings → Secrets and variables → Actions → Variables** and add a repository variable named `BACKEND_URL` with the Render service URL.
3. Merge the deployment workflow into `main`, or run **Deploy GitHub Pages** from the Actions tab after it is on `main`.
4. Visit `https://abhinav6927.github.io/Load_Balancer/`. Enter the same `CONTROL_TOKEN` value set in Render.

The Pages workflow builds the frontend configuration from `BACKEND_URL`; it never writes the control token into the public site. Keep the token private and rotate it in Render if it is exposed.

## Local development

The checked-in `frontend/config.js` defaults to `http://localhost:8000` with token protection disabled. The deployment workflow replaces it only in the Pages build artifact.
