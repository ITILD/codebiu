/**
 * OCR相关的API接口
 */
import type { Language, OcrResponse, OcrResponseWithTranslation } from '../types/ocr';
import { http_base_server } from '@/common/api/http';

/** 获取OCR支持的语言列表 */
export const listOcrLanguages = async () => {
 return http_base_server.get<Language[]>('/ai/ocr/languages');
};

/** 对图片执行OCR识别(识别+分段+版面分析) */
export const recognizeText = async (formData: FormData) => {
  return http_base_server.post<OcrResponse>('/ai/ocr/all', formData);
}

/** 识别图片文字并翻译为目标语言 */
export const recognizeAndTranslate = async (formData: FormData) => {
  return http_base_server.post<OcrResponseWithTranslation>('/ai/translate/ocr', formData);
}
