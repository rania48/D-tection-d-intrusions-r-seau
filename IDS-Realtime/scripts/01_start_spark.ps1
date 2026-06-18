cd "C:\Users\Rania\OneDrive\Bureau\IDS-Realtime"

$env:HADOOP_HOME="C:\hadoop"
$env:hadoop_home_dir="C:\hadoop"
$env:SPARK_HOME="C:\Users\Rania\AppData\Roaming\Python\Python312\site-packages\pyspark"
$env:PYSPARK_PYTHON="python"
$env:PYSPARK_DRIVER_PYTHON="python"
$env:PATH="C:\hadoop\bin;$env:SPARK_HOME\bin;$env:PATH"
$env:JAVA_TOOL_OPTIONS="-Djava.library.path=C:\hadoop\bin"

Remove-Item -Recurse -Force checkpoints -ErrorAction SilentlyContinue

spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.2 spark\spark_streaming_prediction.py
