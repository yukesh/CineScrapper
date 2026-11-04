# Configuration

CineScrapperPy reads `cinescrapper.properties` from the project root, regardless of the current working directory. Create this file locally in a text editor. It is ignored by Git. The URI values stay in environment variables; the properties file maps profile names to variable names.

## MongoDB settings

Use `[mongodb.uris]` to map named profiles to environment-variable names. For example, the local file can contain:

```ini
[mongodb]
uri_profile = cloud
database = cine_info
collection = thamizh

[mongodb.uris]
cloud = MONGODB_URI_CLOUD_FREE
mylocal = MONGODB_URI_MYLOCAL
```

Set the actual URI values in your environment. For zsh, you can define them in `~/.zshrc`, then load them in the current terminal with `source ~/.zshrc`. With `uri_profile = cloud`, the application reads the value of `MONGODB_URI_CLOUD_FREE`. Set `uri_profile = mylocal` or pass `--mongo-uri-profile mylocal` to use the local connection instead. `MONGODB_URI` is also accepted as a general fallback.

Database and utility collection settings resolve from properties first, then `MONGODB_DATABASE` and `MONGODB_COLLECTION`. When MongoDB is enabled, missing required values produce a clear error. The scraper's collection defaults to the selected lowercase language; `--mongo-collection` overrides it.

## Scraper settings

The `[scraper]` section supports `batch_size`, `wiki_rate_limit`, `apple_music_rate_limit`, `rate_limit_jitter`, `max_retries`, `retry_base_delay`, `retry_max_delay`, `cache_ttl_seconds`, and `request_timeout`. Command-line flags override these settings.
