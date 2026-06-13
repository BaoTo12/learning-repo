package ThreadLocal;

public class ThreadLocalDemo {


    public static void main(String[] args) {
        ThreadLocal<String> threadLocal = new ThreadLocal<>();
        threadLocal.set("A thread local value");

        String threadLocalValue =  threadLocal.get();

        threadLocal.remove();

        // ? Ways to set initial value for ThreadLocal
        // ? Overriding initialValue
        ThreadLocal<String> myThreadLocal = new ThreadLocal<>(){
            @Override
            protected String initialValue() {
                return String.valueOf(System.currentTimeMillis());
            }
        };

        // ? Using Supplier Implementation
        ThreadLocal<String> threadLocal1 =
                ThreadLocal.withInitial(() -> String.valueOf(System.currentTimeMillis()));



    }
}
