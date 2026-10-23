#pragma once
#include "kalman_core.h"
void egoLinkImu(const Axis3f *, const Axis3f *, bool);
void egoLinkTof(float);
void egoLinkReset(void);
void egoLinkCommit(const kalmanCoreData_t *, bool);
