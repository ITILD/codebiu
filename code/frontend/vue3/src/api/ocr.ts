/**
 * OCR相关的API接口
 */
import type { Language, OcrResponse, OcrResponseWithTranslation } from '@/types/ocr';
import { http_base_server } from '@/utils/http';
// 获取支持的语言列表
export const fetchLanguages = async () => {
 return http_base_server.get<Language[]>('/ai/ocr/lang');
};


// 执行OCR识别
export const performOCR = async (formData: FormData) => {
  return http_base_server.post<OcrResponse>('/ai/ocr/all', formData);
}

// 执行OCR识别并翻译
export const performOCRWithTranslation = async (formData: FormData) => {
  debugger
  return http_base_server.post<OcrResponseWithTranslation>('/ai/translate/ocr', formData);
}