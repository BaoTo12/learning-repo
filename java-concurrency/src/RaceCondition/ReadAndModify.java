package RaceCondition;

public class ReadAndModify {
    public static void main(String[] args) {

    }
}


class Counter{
    protected long count = 0;
    public void add(long value){
        this.count = this.count + value;
    }
}