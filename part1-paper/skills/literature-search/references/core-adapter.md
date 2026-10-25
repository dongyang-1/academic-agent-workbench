# CORE Adapter

- Endpoint: `GET https://api.core.ac.uk/v3/search/works/`
- Authentication: `Authorization: Bearer <CORE_API_KEY>`.
- Read the key from the environment only; never place it in URLs, logs, JSON, YAML, or Markdown.
- Normalize works to `LiteratureRecord` and retain CORE-specific provider fields in `source_specific`.
- Prefer direct repository PDF URLs from `sourceFulltextUrls`; otherwise retain CORE's authenticated `downloadUrl`.
- Download only explicitly exposed open-access files and preserve the source URL in the download manifest.
