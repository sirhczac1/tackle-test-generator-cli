/*
 * This Java source file was generated by the Gradle 'init' task.
 */
package splitNjoin.app;

import splitNjoin.list.LinkedList;

import static splitNjoin.utilities.StringUtils.join;
import static splitNjoin.utilities.StringUtils.split;
import static splitNjoin.app.MessageUtils.getMessage;

import org.apache.commons.lang3.StringUtils;

public class App {
    public static void main(String[] args) {
        LinkedList tokens;
        tokens = split(getMessage());
        String result = join(tokens);
        System.out.println(StringUtils.capitalize(result));
    }
}