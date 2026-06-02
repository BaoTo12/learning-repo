package createThread;

public class DemoCreatingThread {
    public static void main(String[] args) {
//        Thread thread = new Thread(){
//            @Override
//            public void run() {
//                System.out.println("MyThread running");
//            }
//        };
//
//        thread.start();
//
//        Runnable runnable = () -> {
//            System.out.println("Lambda Runnable is running");
//        };
//
//        Thread exWithRunnable = new Thread(runnable);
//
//        exWithRunnable.start();
//        Thread thread = new Thread("My Thread"){
//            @Override
//            public void run() {
//                System.out.println("Hello" + getName());
//            }
//        };
//
//        thread.start();
//        System.out.println(thread.getName());

        // ? Get the current thread executing the current given block of code
        Thread thread = Thread.currentThread();
        System.out.println(thread.getName());
    }
}



class MyRunnable implements Runnable {
    public void run(){
        System.out.println("MyRunnable running");
    }
}