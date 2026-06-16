package JavaThreadSignaling;

public class MyWaitNotify {
    MonitorObject myMonitorObject = new MonitorObject();

    public void doWait(){
        synchronized(myMonitorObject){
            try{
                myMonitorObject.wait();
            } catch(InterruptedException e){}
        }
    }


    public void doNotify(){
        synchronized(myMonitorObject){
            myMonitorObject.notify();
        }
    }
}
