package com.chibao;

public class ThreadLocalAPI {
    public static void main(String[] args) {
        ThreadLocal<Integer> threadLocal = ThreadLocal.withInitial(() -> 1);
        threadLocal.set(42);

        Integer result = threadLocal.get();

        threadLocal.remove();
    }
}
