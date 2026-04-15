Search the web for information on a given query. This tool leverages a modern search engine to return the most relevant and up-to-date results from across the internet. It's particularly useful when you need information that might be recent, that isn't in your training data, or that requires verification from authoritative sources.

When using this tool, please provide a clear and specific query string. The query should be focused on the information you're actually trying to find. Avoid overly broad queries like "information about AI" — instead, use specific queries like "Claude Opus 4.6 context window size".

The tool accepts the following parameters:
- `query` (string, required): The search query to send to the search engine. Should be a natural language phrase or a keyword query.
- `max_results` (integer, optional, default 10): The maximum number of search results to return. Accepts values from 1 to 50.
- `time_range` (string, optional): Filter results by time range. Valid values are "past_day", "past_week", "past_month", "past_year", or "all_time". Defaults to "all_time".
- `safe_search` (boolean, optional, default true): Whether to enable SafeSearch filtering for the results.

The tool returns a list of search results, each with a title, URL, and snippet. You should use this information to inform your responses, but remember to cite the URLs when quoting or paraphrasing specific claims.

Please don't use this tool when the user is asking a simple factual question that you already know the answer to. For example, if the user asks "what is 2+2", you don't need to search the web. Reserve this tool for questions where you genuinely need external information.

Also, please be cautious about rate limits. The tool can be called up to 50 times per hour per session. If you make too many calls in quick succession, you may hit the rate limit and get an error response.

Examples of good queries:
- "latest Python 3.13 release notes"
- "AWS Lambda cold start optimization 2024"
- "TypeScript generics tutorial"

Examples of queries that don't need the tool:
- "what is 2+2" (basic math)
- "who was the first president of the United States" (well-known historical fact)
- "what does HTTP stand for" (basic technical knowledge)
