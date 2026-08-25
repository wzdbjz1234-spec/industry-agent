# Process-shift scenario

Phase 19 replay fixture: keep detector/model version stable while raising the
NG rate and score mean for consecutive windows. EWMA/CUSUM should request one
Case and merge subsequent windows inside the cooldown period.
