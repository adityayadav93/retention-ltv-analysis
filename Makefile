.PHONY: all data warehouse notebook dashboard deck clean

all: data warehouse notebook dashboard deck

data:        ## 1. generate synthetic SaaS billing + usage data (deterministic, seed 42)
	python src/generate_data.py

warehouse:   ## 2. create schema, load CSVs, run sql/analytics_queries.sql -> data/processed/
	python src/build_warehouse.py

notebook:    ## 3. execute the analysis notebook in place (figures, metrics.json, dashboard extracts)
	jupyter nbconvert --to notebook --execute --inplace notebooks/eda_churn_modeling.ipynb

dashboard:   ## 4. build the self-contained interactive dashboard
	python src/build_dashboard.py

deck:        ## 5. build the 5-slide executive PDF
	python src/build_deck.py

clean:
	rm -rf data/raw data/processed data/warehouse.duckdb
