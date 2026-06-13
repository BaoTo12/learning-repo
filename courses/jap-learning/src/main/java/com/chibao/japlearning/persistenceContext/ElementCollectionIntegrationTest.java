package com.chibao.japlearning.persistenceContext;

import java.util.Arrays;

public class ElementCollectionIntegrationTest {

    private EmployeeRepository employeeRepository;

}

class Solution {
    public void moveZeroes(int[] nums) {
        int k = 0;

        for (int i = 0; i < nums.length; i++) {
            if (nums[i] != 0) {
                nums[k] = nums[i];
                k++;
            }
        }
        while (k < nums.length){
            nums[k++] = 0;
        }
    }
}

 class Main {
    public static void main(String[] args) {
        int[] nums = {0, 1, 0, 3, 12};

        Solution solution = new Solution();
        solution.moveZeroes(nums);

        System.out.println(Arrays.toString(nums));
    }
}