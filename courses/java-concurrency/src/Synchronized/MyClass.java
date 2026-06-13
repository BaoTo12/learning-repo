package Synchronized;

public class MyClass {

    public synchronized void log1(String msg1, String msg2){
       //
    }


    public void log2(String msg1, String msg2){
        synchronized(this){
            //
        }
    }
}