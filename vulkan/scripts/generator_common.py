#!/usr/bin/env python3
#
# Copyright 2019 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This script provides the common functions for generating the
# vulkan framework directly from the vulkan registry (vk.xml).

from subprocess import check_call

copyright = """/*
 * Copyright 2016 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

"""

warning = '// WARNING: This file is generated. See ../README.md for instructions.\n\n'

blacklistedExtensions = [
    'VK_EXT_acquire_xlib_display',
    'VK_EXT_direct_mode_display',
    'VK_EXT_display_control',
    'VK_EXT_display_surface_counter',
    'VK_EXT_full_screen_exclusive',
    'VK_EXT_headless_surface',
    'VK_EXT_metal_surface',
    'VK_FUCHSIA_imagepipe_surface',
    'VK_GGP_stream_descriptor_surface',
    'VK_KHR_display',
    'VK_KHR_display_swapchain',
    'VK_KHR_external_fence_win32',
    'VK_KHR_external_memory_win32',
    'VK_KHR_external_semaphore_win32',
    'VK_KHR_mir_surface',
    'VK_KHR_wayland_surface',
    'VK_KHR_win32_keyed_mutex',
    'VK_KHR_win32_surface',
    'VK_KHR_xcb_surface',
    'VK_KHR_xlib_surface',
    'VK_MVK_ios_surface',
    'VK_MVK_macos_surface',
    'VK_NN_vi_surface',
    'VK_NV_cooperative_matrix',
    'VK_NV_coverage_reduction_mode',
    'VK_NV_external_memory_win32',
    'VK_NV_win32_keyed_mutex',
    'VK_NVX_image_view_handle',
]

exportedExtensions = [
    'VK_ANDROID_external_memory_android_hardware_buffer',
    'VK_KHR_android_surface',
    'VK_KHR_surface',
    'VK_KHR_swapchain',
]

optionalCommands = [
    'vkGetSwapchainGrallocUsageANDROID',
    'vkGetSwapchainGrallocUsage2ANDROID',
]

def runClangFormat(args):
  clang_call = ["clang-format", "--style", "file", "-i", args]
  check_call (clang_call)

def isExtensionInternal(extensionName):
  if extensionName == 'VK_ANDROID_native_buffer':
    return True
  return False

def isFunctionSupported(functionName):
  if functionName not in extensionsDict:
    return True
  else:
    if extensionsDict[functionName] not in blacklistedExtensions:
      return True
  return False

def isInstanceDispatched(functionName):
  return isFunctionSupported(functionName) and getDispatchTableType(functionName) == 'Instance'

def isDeviceDispatched(functionName):
  return isFunctionSupported(functionName) and getDispatchTableType(functionName) == 'Device'

def isGloballyDispatched(functionName):
  return isFunctionSupported(functionName) and getDispatchTableType(functionName) == 'Global'

def isExtensionExported(extensionName):
  if extensionName in exportedExtensions:
    return True
  return False

def isFunctionExported(functionName):
  if isFunctionSupported(functionName):
    if functionName in extensionsDict:
      return isExtensionExported(extensionsDict[functionName])
    return True
  return False

def getDispatchTableType(functionName):
  if functionName not in paramDict:
    return None

  switchCase = {
      'VkInstance ' : 'Instance',
      'VkPhysicalDevice ' : 'Instance',
      'VkDevice ' : 'Device',
      'VkQueue ' : 'Device',
      'VkCommandBuffer ' : 'Device'
  }

  if len(paramDict[functionName]) > 0:
    return switchCase.get(paramDict[functionName][0][0], 'Global')
  return 'Global'

def isInstanceDispatchTableEntry(functionName):
  if functionName == 'vkEnumerateDeviceLayerProperties': # deprecated, unused internally - @dbd33bc
    return False
  if isFunctionExported(functionName) and isInstanceDispatched(functionName):
    return True
  return False

def isDeviceDispatchTableEntry(functionName):
  if isFunctionExported(functionName) and isDeviceDispatched(functionName):
    return True
  return False


def clang_on(f, indent):
  f.write (clang_off_spaces * indent + '// clang-format on\n')

def clang_off(f, indent):
  f.write (clang_off_spaces * indent + '// clang-format off\n')

clang_off_spaces = ' ' * 4

parametersList = []
paramDict = {}
allCommandsList = []
extensionsDict = {}
returnTypeDict = {}
versionDict = {}
aliasDict = {}

def parseVulkanRegistry():
  import xml.etree.ElementTree as ET
  import os
  vulkan_registry = os.path.join(os.path.dirname(__file__),'..','..','..','..','external','vulkan-headers','registry','vk.xml')
  tree = ET.parse(vulkan_registry)
  root = tree.getroot()
  for commands in root.iter('commands'):
    for command in commands:
      if command.tag == 'command':
        parametersList.clear()
        protoset = False
        fnName = ""
        fnType = ""
        if command.get('alias') != None:
          alias = command.get('alias')
          fnName = command.get('name')
          aliasDict[fnName] = alias
          allCommandsList.append(fnName)
          paramDict[fnName] = paramDict[alias].copy()
          returnTypeDict[fnName] = returnTypeDict[alias]
        for params in command:
          if params.tag == 'param':
            paramtype = ""
            if params.text != None and params.text.strip() != '':
              paramtype = params.text.strip() + ' '
            typeval = params.find('type')
            paramtype = paramtype + typeval.text
            if typeval.tail != None:
              paramtype += typeval.tail.strip() + ' '
            pname = params.find('name')
            paramname = pname.text
            if pname.tail != None and pname.tail.strip() != '':
              parametersList.append((paramtype, paramname, pname.tail.strip()))
            else:
              parametersList.append((paramtype, paramname))
          if params.tag == 'proto':
            for c in params:
              if c.tag == 'type':
                fnType = c.text
              if c.tag == 'name':
                fnName = c.text
                protoset = True
                allCommandsList.append(fnName)
                returnTypeDict[fnName] = fnType
        if protoset == True:
          paramDict[fnName] = parametersList.copy()

  for exts in root.iter('extensions'):
    for extension in exts:
      apiversion = ""
      if extension.tag == 'extension':
        extname = extension.get('name')
        for req in extension:
          if req.get('feature') != None:
            apiversion = req.get('feature')
          for commands in req:
            if commands.tag == 'command':
              commandname = commands.get('name')
              if commandname not in extensionsDict:
                extensionsDict[commandname] = extname
                if apiversion != "":
                  versionDict[commandname] = apiversion

  for feature in root.iter('feature'):
    apiversion = feature.get('name')
    for req in feature:
      for command in req:
        if command.tag == 'command':
          cmdName = command.get('name')
          if cmdName in allCommandsList:
            versionDict[cmdName] = apiversion


def initProc(name, f):
  if name in extensionsDict:
    f.write ('    INIT_PROC_EXT(' + extensionsDict[name][3:] + ', ')
  else:
    f.write ('    INIT_PROC(')

  if name in versionDict and versionDict[name] == 'VK_VERSION_1_1':
    f.write('false, ')
  elif name in optionalCommands:
    f.write('false, ')
  else:
    f.write('true, ')

  if isInstanceDispatched(name):
    f.write('instance, ')
  else:
    f.write('dev, ')

  f.write(name[2:] + ');\n')

