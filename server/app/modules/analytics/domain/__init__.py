"""The calculations: pure functions over plain rows. No ORM, no framework, no other module (R9).

A function takes every usable row and the period, and limits the rows to the period itself: the previous
period, the rolling average, outlier windows and recurring rhythm reach before it.
"""
