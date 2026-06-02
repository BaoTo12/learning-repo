package createThread;

public class JavaThreadSimpleExample {
    public static void main(String[] args) {
        System.out.println(Thread.currentThread().getName());

        for (int i = 0; i < 10; i++) {
            Thread thread = new Thread("Thread " + i){
                @Override
                public void run() {
                    System.out.println("Thread Name: " + getName());
                }
            };
            thread.start();
        }

    }
}
