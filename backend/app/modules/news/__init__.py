"""News Ingestion module -- see docs/features/123-news-channel.md.

RSS/Atom feed sources -> deduplicated NewsItem rows a user selects from to
mass-produce short news videos through the existing Factory pipeline. Its
own two tables, no FK into any other app/modules/* table (per
app/modules/README.md, a module may never import another module). The one
composition root allowed to bridge this module with app.modules.beat /
app.modules.batch / app.modules.ai is
app/api/v1/endpoints/news_pipeline.py.
"""
