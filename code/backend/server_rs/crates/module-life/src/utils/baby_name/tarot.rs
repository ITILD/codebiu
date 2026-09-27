//! 塔罗牌计算(对齐 Python tarot.py): 生命灵数(生命路径数) → 生命塔罗牌(经典 numerology 对应)
//!
//! 算法: 出生日期全部数字逐位相加, 迭代至结果 ≤ 22(生命牌区间 1-22, 22 对应 0 号愚者)。

use chrono::Datelike;
use common::utils::error::AppError;

use super::almanac::parse_birth_date;
use crate::do_::almanac::TarotInfo;

/// 数字 → (大阿卡纳牌名, 寓意)
fn tarot_card(num: i32) -> (&'static str, &'static str) {
    match num {
        1 => ("魔术师", "创造力与行动力, 潜能无限, 开创新局"),
        2 => ("女祭司", "直觉与智慧, 静水深流, 内在觉察"),
        3 => ("皇后", "丰饶与慈爱, 温暖包容, 抚育成长"),
        4 => ("皇帝", "秩序与权威, 稳重坚毅, 守护担当"),
        5 => ("教皇", "传统与教化, 心怀信仰, 传道授业"),
        6 => ("恋人", "爱与选择, 真诚以待, 和谐共生"),
        7 => ("战车", "意志与胜利, 勇往直前, 驾驭命运"),
        8 => ("力量", "柔韧与勇气, 以柔克刚, 内在力量"),
        9 => ("隐士", "沉思与追寻, 智慧之光, 独立自省"),
        10 => ("命运之轮", "流转与机遇, 顺势而为, 转折新生"),
        11 => ("正义", "公正与平衡, 明辨是非, 秤心而论"),
        12 => ("倒吊人", "奉献与觉悟, 换位思考, 逆处逢生"),
        13 => ("死神", "蜕变与重生, 告别过往, 浴火新生"),
        14 => ("节制", "调和与净化, 张弛有度, 中道而行"),
        15 => ("恶魔", "欲望与束缚, 认清执着, 破除迷障"),
        16 => ("高塔", "觉醒与突破, 骤变之后, 拨云见日"),
        17 => ("星星", "希望与灵感, 静夜启明, 心怀憧憬"),
        18 => ("月亮", "潜意识与梦境, 情感丰沛, 直觉敏锐"),
        19 => ("太阳", "光明与喜悦, 乐观豁达, 温暖四射"),
        20 => ("审判", "召唤与新生, 反思过去, 迎接使命"),
        21 => ("世界", "圆满与成就, 融合通达, 功成行满"),
        22 => ("愚者", "自由与冒险, 无畏初心, 天地任行"),
        _ => ("", ""),
    }
}

/// 数字各位求和
fn digit_sum(n: i32) -> i32 {
    n.to_string().chars().filter_map(|c| c.to_digit(10)).map(|d| d as i32).sum()
}

/// 生命灵数: 出生日期逐位求和迭代至 ≤22
pub fn life_number(birth_date: &str) -> Result<i32, AppError> {
    let d = parse_birth_date(birth_date)?;
    // YYYYMMDD 逐位求和
    let mut total: i32 = format!("{:04}{:02}{:02}", d.year(), d.month(), d.day())
        .chars()
        .filter_map(|c| c.to_digit(10))
        .map(|x| x as i32)
        .sum();
    while total > 22 {
        total = digit_sum(total);
    }
    Ok(total.max(1))
}

/// 生命塔罗牌信息(生命灵数 → 大阿卡纳牌名/寓意/一句话总结)
pub fn get_tarot(birth_date: &str) -> Result<TarotInfo, AppError> {
    let num = life_number(birth_date)?;
    let (card, meaning) = tarot_card(num);
    Ok(TarotInfo {
        number: num,
        card: card.to_string(),
        meaning: meaning.to_string(),
        // 编号: 22(愚者)对应 0 号
        summary: format!(
            "生命塔罗牌: {card}(编号{})。寓意: {meaning}",
            if num < 22 { num.to_string() } else { "0".to_string() }
        ),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn life_number_iteration() {
        // 2000-01-01 → 2+0+0+0+0+1+0+1=4
        assert_eq!(life_number("2000-01-01").unwrap(), 4);
        // 1999-12-31 → 1+9+9+9+1+2+3+1=35 → 3+5=8
        assert_eq!(life_number("1999-12-31").unwrap(), 8);
        // 最小为 1(日期全为 0 的情况不存在, 但 max 兜底逻辑保持)
        assert_eq!(life_number("2022-02-02").unwrap(), 10);
    }

    #[test]
    fn tarot_number_22_is_fool() {
        // 2025-07-06 数字和恰为 22 → 愚者, 编号显示 0
        let info = get_tarot("2025-07-06").unwrap();
        assert_eq!(info.number, 22);
        assert_eq!(info.card, "愚者");
        assert!(info.summary.contains("编号0"));
        // 2000-06-16 → 15 → 恶魔
        let info15 = get_tarot("2000-06-16").unwrap();
        assert_eq!(info15.number, 15);
        assert_eq!(info15.card, "恶魔");
    }
}
