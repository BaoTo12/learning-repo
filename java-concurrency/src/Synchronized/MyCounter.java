package Synchronized;

public class MyCounter {
    private int count = 0;

    public synchronized void add(int value) {
        synchronized(this){
            this.count += value;
        }
    }

    public synchronized void subtract(int value) {
        this.count -= value;
    }
}
