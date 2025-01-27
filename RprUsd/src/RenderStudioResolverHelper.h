/**********************************************************************
Copyright 2023 Advanced Micro Devices, Inc
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
********************************************************************/


#pragma once

#include <maya/MTimerMessage.h>

#include "Kit.h"

using LiveModeInfo = RenderStudio::Kit::LiveSessionInfo;

class RenderStudioResolverHelper
{
public:
	static void StartLiveMode(const LiveModeInfo& liveModeParams);
	static void StopLiveMode();

	static bool IsUnresovableToRenderStudioPath(const std::string& path);
	static std::string Unresolve(const std::string& path);

	static void SetWorkspacePath(const std::string& path);

private:
	static void LiveModeTimerCallbackId(float, float, void* pClientData);

private:
	static MCallbackId g_LiveModeTimerCallbackId;
	static bool m_IsLiveModeStarted;
};