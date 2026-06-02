package ThreadLocal;

import java.text.SimpleDateFormat;
import java.util.Date;

// ! Lazy Setting of ThreadLocal Value
public class MyDateFormatter {
    private ThreadLocal<SimpleDateFormat> simpleDateFormatThreadLocal = new ThreadLocal<>();

    public String format(Date date) {
        SimpleDateFormat simpleDateFormat = getThreadLocalSimpleDateFormat();
        return simpleDateFormat.format(date);
    }

    private SimpleDateFormat getThreadLocalSimpleDateFormat() {
        SimpleDateFormat simpleDateFormat = simpleDateFormatThreadLocal.get();
        if (simpleDateFormat == null) {
            simpleDateFormat = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
            simpleDateFormatThreadLocal.set(simpleDateFormat);
        }
        return simpleDateFormat;
    }
}
