/**
 * 获取 localStorage 中的所有 key
 * @returns 排序后的键名数组
 */
function getLocalStorageKeys(): string[] {
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key !== null) {
      keys.push(key);
    }
  }
  // 键名按字母顺序排序
  keys.sort();
  return keys;
}

/**
 * 设置 localStorage 项
 * @param key 键名
 * @param value 值，可以是任意可序列化数据
 * @returns 是否设置成功
 */
function setLocalStorageItem<T>(key: string, value: T): boolean {
  try {
    const serializedValue = JSON.stringify(value);
    localStorage.setItem(key, serializedValue);
    return true;
  } catch (error) {
    console.error(`无法设置 localStorage 项 "${key}":`, error);
    return false;
  }
}

/**
 * 获取 localStorage 项
 * @param key 键名
 * @returns 解析后的值或 null（如果不存在或解析失败）
 */
function getLocalStorageItem<T>(key: string): T | null {
  try {
    const storedValue = localStorage.getItem(key);
    if (storedValue === null) {
      return null;
    }
    return JSON.parse(storedValue) as T;
  } catch (error) {
    console.error(`无法获取或解析 localStorage 项 "${key}":`, error);
    return null;
  }
}

/**
 * 移除 localStorage 项
 * @param key 键名
 * @returns 是否移除成功
 */
function removeLocalStorageItem(key: string): boolean {
  try {
    localStorage.removeItem(key);
    return true;
  } catch (error) {
    console.error(`无法移除 localStorage 项 "${key}":`, error);
    return false;
  }
}

/**
 * 清空所有 localStorage 项
 * @returns 是否清空成功
 */
function clearLocalStorage(): boolean {
  try {
    localStorage.clear();
    return true;
  } catch (error) {
    console.error('无法清空 localStorage:', error);
    return false;
  }
}

/**
 * 检查 localStorage 是否可用
 * @returns localStorage 是否可用
 */
function isLocalStorageAvailable(): boolean {
  try {
    const testKey = '__storage_test__';
    localStorage.setItem(testKey, testKey);
    localStorage.removeItem(testKey);
    return true;
  } catch (error) {
    return false;
  }
}

/**
 * 获取 localStorage 占用空间信息
 * @returns 包含总大小、键数量等信息的对象
 */
function getLocalStorageSizeInfo(): {
  totalSize: number;
  keyCount: number;
  usagePercent: number
} {
  let totalSize = 0;
  const keys = getLocalStorageKeys();

  keys.forEach(key => {
    const value = localStorage.getItem(key);
    if (value) {
      totalSize += key.length + value.length;
    }
  });

  // 假设浏览器限制为 5MB (5 * 1024 * 1024 字节)
  const estimatedLimit = 5 * 1024 * 1024;
  const usagePercent = Math.min((totalSize / estimatedLimit) * 100, 100);

  return {
    totalSize,
    keyCount: keys.length,
    usagePercent
  };
}

export {
  getLocalStorageKeys,
  setLocalStorageItem,
  getLocalStorageItem,
  removeLocalStorageItem,
  clearLocalStorage,
  isLocalStorageAvailable,
  getLocalStorageSizeInfo
};
