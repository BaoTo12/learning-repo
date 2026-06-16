package Problems.FalseSharing;

public class Counter {
    // “Hãy chèn thêm padding bytes quanh field / class này để các field không nằm sát nhau trong memory.”
    // --> đẩy các field ra xa nhau để không rơi vào cùng cache line
    @jdk.internal.vm.annotation.Contended
    public volatile long count1 = 0;
    public volatile long count2 = 0;
}
