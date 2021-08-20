import logging, re
import apache_beam as beam
from apache_beam.io import WriteToText
from apache_beam.io.gcp.bigquery import ReadFromBigQuery, WriteToBigQuery

class MakeLocation(beam.DoFn):
  def process(self, element):
    id = element['id']
    Province_State = element['Province_State']
    Country_Region = element['Country_Region']

    if id != None and Province_State != None and Country_Region != None:
        record = {'id': id, 'Province_State': Province_State, 'Country_Region' : Country_Region}
        return [(id, record)]
    if id == None:
        record = {'id': 'None', 'Province_State': Province_State, 'Country_Region' : Country_Region}
        return [(id, record)]
    
class MakeUniqueLocation(beam.DoFn):
  def process(self, element):
     
     id, location = element 
     location_list = list(location) 
  
     return [location_list[0]]

def run():
    PROJECT_ID = 'lone-ranger'
    BUCKET = 'gs://lone-ranger-bucket/temp'

    options = {
     'project': PROJECT_ID
    }
    opts = beam.pipeline.PipelineOptions(flags=[], **options)

    p = beam.Pipeline('DirectRunner', options=opts)
    
    # get data from big query

    sql = 'SELECT id, Province_State, Country_Region FROM JHU_refined.CovidLocation limit 52'
    bq_source = ReadFromBigQuery(query=sql, use_standard_sql=True, gcs_location=BUCKET)

    query_results = p | 'Read from BQ' >> beam.io.Read(bq_source)
    
    #Pass PCollection into MakeLocation: result is all the locations with primary key

    location_pcoll = query_results | 'Make Location' >> beam.ParDo(MakeLocation())
    
    grouped_location_pcoll = location_pcoll | 'GroupByKey' >> beam.GroupByKey()

    grouped_location_pcoll | 'Log covid location group output' >> WriteToText('covidlocation_output.txt')
    
    # group by key Geo_ID and pass PCollection into MakeUniqueLocation to make sure all pk are unique
    
    unique_location_pcoll = grouped_location_pcoll | 'Make Unique Location' >> beam.ParDo(MakeUniqueLocation())
    
    unique_location_pcoll | 'Log covid location unique' >> WriteToText('covidlocation_unique_output.txt')

    # write to big query with correct name and schema
    
    dataset_id = 'JHU_refined'
    table_id = PROJECT_ID + ':' + dataset_id + '.' + 'CovidLocation_Beam'
    schema_id = 'id:INTEGER,Province_State:STRING,Country_Region:STRING'

    unique_location_pcoll | 'Write takes to BQ' >> WriteToBigQuery(table=table_id, schema=schema_id, custom_gcs_temp_location=BUCKET)
     
    result = p.run()
    result.wait_until_finish()      


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.ERROR)
    run()