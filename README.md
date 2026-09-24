# Bhuwan APIs UI

Mobile-first API testing dashboard matching the supplied screenshots.

## Run
```bash
npm install
npm start
```
Then open `http://localhost:3000`.

## Add your own APIs
Edit `server.js` and add objects to `APIS`. URL placeholders such as `{uid}`, `{pass}`, `{region}` become input fields.

The server makes the upstream request, so the browser does not need CORS permission from the target API. Upstream status codes and response bodies are shown in the Test Console, including JSON such as:
`{"error":"HTTP 400 - Bad Request"}`.
