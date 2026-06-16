package createThread;

public class CreatingVirtualThread {
    public static void main(String[] args) throws InterruptedException {
        Runnable runnable = new Runnable() {
            @Override
            public void run() {
                try {
                    Thread.sleep(3L * 1000);
                } catch (InterruptedException e) {
                    throw new RuntimeException(e);
                }
                System.out.println("Runnable Thread");
            }
        };

        Thread vThread = Thread.ofVirtual().unstarted(runnable);

        vThread.start();
        vThread.join();
    }
}
