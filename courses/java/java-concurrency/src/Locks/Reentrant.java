package Locks;

public class Reentrant {

    // ! If a thread already holds the lock on a monitor object,
    // ! it has access to all blocks synchronized on the same monitor object.
    // ! This is called reentrance
    public synchronized void outer() {
        inner();
    }

    public synchronized void inner() {
        //do something
    }
}

