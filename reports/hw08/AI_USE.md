# AI_USE - HW8

1. What AI helped with / what I did  
   I used Cursor to help wire Kafka RPC and the three agents from the class demos. 

2. One wrong or independently verified item  
   Early compose advertised Kafka as `localhost:9092` while the worker ran inside Docker, so the worker never got requests. Also an early Part 3 ordering run wrote empty CSVs because the Writer processes had already died.

3. How I detected / verified it  
   `homework_demo.py` timed out and worker logs stayed quiet. For ordering, the CSV files only had headers.

4. What I changed  
   Split listeners so containers use `kafka:9092` and the host uses `localhost:9092`. For Part 3, `run_failure_tests.py` starts two Writer processes itself, waits for DLQ + both ordering runs, then stops them.
