package Synchronized;

public class MyStaticCounter {
    private static int count = 0;

    public static synchronized void add(int value){
        count += value;
    }

    public static synchronized void subtract(int value){
        count -= value;
    }
}
