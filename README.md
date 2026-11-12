# WeatherPipeline

A small batch data pipeline that extracts hourly weather data for four Norwegian cities, cleans it with pandas and stores it as Parquet. It is a learning project in data engineering, built step by step, and the notes below explain the key concepts behind the design choices.

## Data source

Weather data comes from the [Open-Meteo](https://open-meteo.com/) forecast API, which is free and requires no API key. For each of Oslo, Bergen, Trondheim and Tromsø, the pipeline requests hourly temperature (`temperature_2m`), precipitation and wind speed (`wind_speed_10m`) for the past seven days, using the `Europe/Oslo` time zone.

## Running the pipeline

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python pipeline.py
```

The output is written to the folder `data/` (not version controlled).

## ETL vs. ELT

ETL (Extract Transform Load) was the standard for data pipelines before the dawn of cloud computing. This ensured that the data stored was in the right format based on rigid rules which were applied before the data was stored. This saved costs related to storage and fitted the business logic to query it. Even in today's cloud compute world with cheap storage, using ETL is beneficial for use cases such as health care records and financial transactions which require compliance.

ELT (Extract Load Transform) emerged from cheap storage and scalability of cloud computing. This made it possible for multiple teams to access the data, quickly change the business logic and to experiment with the data set. With ELT the raw data is stored without transformation, so nothing is lost in the gathering phase. Different queries can then be run on the data based on changing business needs.

## Batch vs. streaming data pipelines

Batch is like looking in the rear view mirror. Data is collected in large chunks over a longer period, like hours, days or months. You're looking at historical data to make sense of what happened. It's slow, steady and cost effective, making it great for monthly reports, statements and finding trends. Simple processing logic and easier to maintain. This app uses the data from Open-Meteo in a batch pipeline.

Streaming happens in near real time and is for acting on data instantly. Data is collected continuously event-by-event and gives real-time insights. Perfect for suggesting related products at an e-commerce site while the user is adding goods to their shopping cart. 

The real trick for businesses is to use these two approaches in combination, leveraging the best from both, in a Lambda architecture. 

## Data lake vs. data warehouse

A data lake stores raw, unstructured or structured data in its original format for future use and uses schema-on-read. A file format widely used for this kind of data is Apache Parquet. A data warehouse on the other hand stores structured, cleaned and processed data ready for business reporting and uses schema-on-write.

Data lakes' main use cases are machine learning and deep data analysis, while data warehouses are more for business intelligence, fast SQL queries and dashboards.

There are available hybrid options called lakehouses which put a data warehouse as a layer on top of the data lake.

## CSV vs. Parquet

Saving the extracted data to both CSV and Parquet shows that when in CSV format all the types are stripped and when reading it back in you'll have to guess what format it's in. In addition to saving all the formats for the data, the file size of the Parquet file is considerably smaller, even with the small number of entries we got here. In my limited experiment with just 1344 data point the Parquet file was 4.7x smaller than the CSV file.
