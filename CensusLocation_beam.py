import logging, re
import apache_beam as beam
from apache_beam.io import WriteToText
from apache_beam.io.gcp.bigquery import ReadFromBigQuery, WriteToBigQuery

class MakeLocation(beam.DoFn):
  def process(self, element):
    Geo_ID = element['Geo_ID']
    GeoName = element['GeoName']

    if Geo_ID != None and GeoName != None:
        record = {'Geo_ID': Geo_ID, 'GeoName': GeoName}
        return [(Geo_ID, record)]
    if Geo_ID == None or GeoName == None:
        record = {'Geo_ID': 'None', 'GeoName': 'None'}
        return [(Geo_ID, record)]
    
class MakeUniqueLocation(beam.DoFn):
  def process(self, element):
     
     Geo_ID, location = element 
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

    sql = 'SELECT Geo_ID, GeoName FROM Census_refined.CensusLocation limit 52'
    bq_source = ReadFromBigQuery(query=sql, use_standard_sql=True, gcs_location=BUCKET)

    query_results = p | 'Read from BQ' >> beam.io.Read(bq_source)
    
    #Pass PCollection into MakeLocation: result is all the locations with primary key

    location_pcoll = query_results | 'Make Location' >> beam.ParDo(MakeLocation())
    
    grouped_location_pcoll = location_pcoll | 'GroupByKey' >> beam.GroupByKey()

    grouped_location_pcoll | 'Log location group output' >> WriteToText('censuslocation_output.txt')
    
    # group by key Geo_ID and pass PCollection into MakeUniqueLocation to make sure all pk are unique
    
    unique_location_pcoll = grouped_location_pcoll | 'Make Unique Location' >> beam.ParDo(MakeUniqueLocation())
    
    unique_location_pcoll | 'Log location unique' >> WriteToText('location_unique_output.txt')
    
    # write to big query with correct name and schema

    dataset_id = 'Census_refined'
    table_id = PROJECT_ID + ':' + dataset_id + '.' + 'CensusLocation_Beam'
    schema_id = 'Geo_ID:STRING,GeoName:STRING'

    unique_location_pcoll | 'Write takes to BQ' >> WriteToBigQuery(table=table_id, schema=schema_id, custom_gcs_temp_location=BUCKET)
     
    result = p.run()
    result.wait_until_finish()      


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.ERROR)
    run()