package Problems.FalseSharing;

public class FalseSharingExample {
    public static void main(String[] args) {
        Counter counter1 = new Counter();
        Counter counter2 = counter1;

        long iterations = 1_000_000_000;

        Thread thread1 = new Thread(() -> {
            long startTime = System.currentTimeMillis();
            for (int i = 0; i < iterations; i++) {
                counter1.count1++;
            }
            long endTime = System.currentTimeMillis();
            System.out.println("total time: " + (endTime - startTime));
        });

        Thread thread2 = new Thread(() -> {
            long startTime = System.currentTimeMillis();
            for(long i=0; i<iterations; i++) {
                counter2.count2++;
            }
            long endTime = System.currentTimeMillis();
            System.out.println("total time: " + (endTime - startTime));
        });

        thread1.start();
        thread2.start();
    }
}
