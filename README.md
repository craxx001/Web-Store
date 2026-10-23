# IND Like API

Configure `API_KEY` as an environment variable before deployment.
Add token objects to `tokens.json` in this format:

```json
[
  {"token": "YOUR_TOKEN_HERE"}
]
```

Endpoint: `/like?uid=PLAYER_UID&key=YOUR_API_KEY`

The API is configured for the IND region only.
