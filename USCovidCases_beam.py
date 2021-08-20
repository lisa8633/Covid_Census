import logging, re
import apache_beam as beam
from apache_beam.io import WriteToText
from apache_beam.io.gcp.bigquery import ReadFromBigQuery, WriteToBigQuery

class RoundDecimals(beam.DoFn):
  def process(self, element):
    id = element['id']
    
    # Round and store rounded values in element
    element['Mortality_Rate'] = round(element['Mortality_Rate'], 2)
    element['Testing_Rate'] = round(element['Testing_Rate'], 2)
    
    return [element]

class MakeRecords(beam.DoFn):
  def process(self, element):
    id = element['id']
    record = element

    if id == None:
        record['id'] = 'None'
        id = 'None'
    
    return [(id, record)]
    
class PickUniqueRecord(beam.DoFn):
  def process(self, element):
     
     id, location = element 
     location_list = list(location) 
     
     if id != 'None': #Skips records without a primary key
         return [location_list[0]] #Returns first record in each potential set of records with one primary key

def run():
    PROJECT_ID = 'lone-ranger'
    BUCKET = 'gs://lone-ranger-bucket/temp'

    options = {
     'project': PROJECT_ID
    }
    
    opts = beam.pipeline.PipelineOptions(flags=[], **options)

    p = beam.Pipeline('DirectRunner', options=opts)
    
    # get data from big query

    sql = 'SELECT * FROM JHU_refined.USCovidCases limit 450'
    bq_source = ReadFromBigQuery(query=sql, use_standard_sql=True, gcs_location=BUCKET)

    query_results = p | 'Read from BQ' >> beam.io.Read(bq_source)
    
    # Pass Pcollection into RoundDecimals: result features all records with rounded mortality and testing rates
    
    rounded_pcoll = query_results | 'Round rates' >> beam.ParDo(RoundDecimals())
    
    rounded_pcoll | 'Log rounded data output' >> WriteToText('uscovidcases_rounded_output.txt')
    
    #Pass PCollection into MakeRecords, then GroupByKey: result is a tuple with (primary key, [list of records with key])

    tupled_pcoll = rounded_pcoll | 'Make Records' >> beam.ParDo(MakeRecords())
    
    grouped_tupled_pcoll = tupled_pcoll | 'GroupByKey' >> beam.GroupByKey()

    grouped_tupled_pcoll | 'Log key grouped output' >> WriteToText('uscovidcases_key_grouped_output.txt')
    
    # Pass PCollection into PickUniqueRecord to make sure one record is picked for each pk
    
    unique_record_pcoll = grouped_tupled_pcoll | 'Pick Unique Record' >> beam.ParDo(PickUniqueRecord())
    
    unique_record_pcoll | 'Log unique records' >> WriteToText('uscovidcases_unique_output.txt')

    # write to big query with correct name and schema
    
    dataset_id = 'JHU_refined'
    table_id = PROJECT_ID + ':' + dataset_id + '.' + 'USCovidCases_Beam'
    schema_id = 'id:INTEGER,l_id:INTEGER,Last_Update:TIMESTAMP,Confirmed:INTEGER,Deaths:INTEGER,Recovered:INTEGER,Active:INTEGER,People_Tested:INTEGER,Mortality_Rate:FLOAT,Testing_Rate:FLOAT'

    unique_record_pcoll | 'Write takes to BQ' >> WriteToBigQuery(table=table_id, schema=schema_id, custom_gcs_temp_location=BUCKET)
     
    result = p.run()
    result.wait_until_finish()    


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.ERROR)
    run()