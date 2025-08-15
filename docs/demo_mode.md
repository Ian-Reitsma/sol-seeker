# Demo Mode

The dashboard supports a paper-trading mode that lets users explore the interface without placing real orders. When switching to demo mode in the settings panel, the client now validates selected assets before sending them to the server.

- The list of supported symbols is fetched from `/assets` when the settings panel opens.
- `saveMode()` rejects any symbol not returned by this endpoint and displays a toast error.
- The **Save** button stays disabled until all selected assets are valid.

These client-side checks prevent accidental typos from reaching the backend.
