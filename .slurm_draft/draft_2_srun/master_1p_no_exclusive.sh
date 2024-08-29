
echo "launch proc 0"
srun --ntasks=1 --qos c1_inter_giga -l bash worker.sh 0 &
echo "detach proc 0"

echo "launch proc 1"
srun --ntasks=1 --qos c1_inter_giga -l bash worker.sh 1 &
echo "detach proc 1"

echo "launch proc 2"
srun --ntasks=1 --qos c1_inter_giga -l bash worker.sh 2 &
echo "detach proc 2"

echo "launch proc 3"
srun --ntasks=1 --qos c1_inter_giga -l bash worker.sh 3 &
echo "detach proc 3"

wait
