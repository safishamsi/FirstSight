package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.R

object OpsColor {
    val Canvas = Color(0xFFF0F0F0)
    val Panel = Color(0xFFF8F8F8)
    val Border = Color(0xFF222222)
    val BorderMuted = Color(0xFF969696)
    val Ink = Color(0xFF111111)
    val MutedInk = Color(0xFF585858)
    val Accent = Color(0xFF233BDB)
    val AccentSoft = Color(0xFFDCE2FF)
    val Success = Color(0xFFD6F07D)
    val Warning = Color(0xFFF1EF6A)
    val Danger = Color(0xFFC8452C)
    val Overlay = Color(0xCC111111)
}

@Composable
fun OpsScreen(
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    Box(
        modifier =
            modifier
                .fillMaxSize()
                .background(OpsColor.Canvas)
                .drawBehind {
                    val step = 24.dp.toPx()
                    val dot = 2.dp.toPx()
                    var x = 0f
                    while (x <= size.width) {
                        drawLine(
                            color = OpsColor.Border.copy(alpha = 0.06f),
                            start = androidx.compose.ui.geometry.Offset(x, 0f),
                            end = androidx.compose.ui.geometry.Offset(x, size.height),
                            strokeWidth = 1f,
                        )
                        x += step
                    }
                    var y = 0f
                    while (y <= size.height) {
                        drawLine(
                            color = OpsColor.Border.copy(alpha = 0.06f),
                            start = androidx.compose.ui.geometry.Offset(0f, y),
                            end = androidx.compose.ui.geometry.Offset(size.width, y),
                            strokeWidth = 1f,
                        )
                        y += step
                    }
                    var dotX = step / 2f
                    while (dotX <= size.width) {
                        var dotY = step / 2f
                        while (dotY <= size.height) {
                            drawCircle(
                                color = OpsColor.Border.copy(alpha = 0.10f),
                                radius = dot,
                                center = androidx.compose.ui.geometry.Offset(dotX, dotY),
                                style = Stroke(width = 0f),
                            )
                            dotY += step
                        }
                        dotX += step
                    }
                },
        content = content,
    )
}

@Composable
fun OpsTopBar(
    title: String,
    subtitle: String,
    modifier: Modifier = Modifier,
    leading: @Composable (() -> Unit)? = null,
    trailing: @Composable RowScope.() -> Unit = {},
) {
    Row(
        modifier =
            modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top,
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            leading?.invoke()
            Icon(
                painter = painterResource(R.drawable.camera_access_icon),
                contentDescription = null,
                tint = OpsColor.Accent,
                modifier = Modifier.size(20.dp),
            )
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    text = title,
                    color = OpsColor.Ink,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                )
                Text(
                    text = subtitle,
                    color = OpsColor.MutedInk,
                    fontSize = 11.sp,
                    lineHeight = 14.sp,
                )
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp), content = trailing)
    }
}

@Composable
fun OpsIconAction(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Box(
        modifier =
            modifier
                .size(36.dp)
                .border(1.dp, OpsColor.Border, RoundedCornerShape(2.dp))
                .background(Color.White)
                .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        content()
    }
}

@Composable
fun OpsPanel(
    modifier: Modifier = Modifier,
    contentPadding: PaddingValues = PaddingValues(12.dp),
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .border(1.dp, OpsColor.Border)
                .background(Color.White)
                .padding(contentPadding),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        content = content,
    )
}

@Composable
fun OpsSectionHeader(
    title: String,
    modifier: Modifier = Modifier,
    trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = title.uppercase(),
            color = OpsColor.Ink,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 12.sp,
        )
        trailing?.invoke()
    }
}

@Composable
fun OpsBodyText(
    text: String,
    modifier: Modifier = Modifier,
    muted: Boolean = true,
) {
    Text(
        text = text,
        color = if (muted) OpsColor.MutedInk else OpsColor.Ink,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        modifier = modifier,
    )
}

@Composable
fun OpsTag(
    label: String,
    modifier: Modifier = Modifier,
    background: Color = OpsColor.AccentSoft,
    foreground: Color = OpsColor.Ink,
) {
    Text(
        text = label.uppercase(),
        color = foreground,
        fontFamily = FontFamily.Monospace,
        fontSize = 10.sp,
        fontWeight = FontWeight.Bold,
        modifier =
            modifier
                .background(background, RoundedCornerShape(2.dp))
                .padding(horizontal = 6.dp, vertical = 4.dp),
    )
}

@Composable
fun OpsPrimaryButton(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    isDestructive: Boolean = false,
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.heightIn(min = 44.dp),
        shape = RoundedCornerShape(2.dp),
        colors =
            ButtonDefaults.buttonColors(
                containerColor = if (isDestructive) OpsColor.Danger else OpsColor.Accent,
                contentColor = Color.White,
                disabledContainerColor = OpsColor.BorderMuted,
                disabledContentColor = Color.White,
            ),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 10.dp),
    ) {
        Text(
            text = label.uppercase(),
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 12.sp,
        )
    }
}

@Composable
fun OpsSecondaryButton(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.heightIn(min = 40.dp),
        shape = RoundedCornerShape(2.dp),
        border = BorderStroke(1.dp, OpsColor.Border),
        colors =
            ButtonDefaults.buttonColors(
                containerColor = Color.White,
                contentColor = OpsColor.Ink,
                disabledContainerColor = Color.White,
                disabledContentColor = OpsColor.BorderMuted,
            ),
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
    ) {
        Text(
            text = label.uppercase(),
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 11.sp,
        )
    }
}

@Composable
fun OpsTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    singleLine: Boolean = true,
    minLines: Int = 1,
    keyboardType: KeyboardType = KeyboardType.Text,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = {
            Text(
                text = label.uppercase(),
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp,
            )
        },
        singleLine = singleLine,
        minLines = minLines,
        modifier = modifier.fillMaxWidth(),
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
        textStyle = androidx.compose.ui.text.TextStyle(
            color = OpsColor.Ink,
            fontSize = 13.sp,
            fontFamily = if (minLines > 1) FontFamily.Monospace else FontFamily.Default,
        ),
    )
}

@Composable
fun OpsChoiceRow(
    options: List<String>,
    selected: String,
    onSelected: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        options.forEach { option ->
            val isSelected = selected == option
            Button(
                onClick = { onSelected(option) },
                shape = RoundedCornerShape(2.dp),
                border = BorderStroke(1.dp, OpsColor.Border),
                colors =
                    ButtonDefaults.buttonColors(
                        containerColor = if (isSelected) OpsColor.Accent else Color.White,
                        contentColor = if (isSelected) Color.White else OpsColor.Ink,
                    ),
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 8.dp),
            ) {
                Text(
                    text = option.uppercase(),
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    fontSize = 11.sp,
                )
            }
        }
    }
}

@Composable
fun OpsSwitchRow(
    label: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
    detail: String? = null,
) {
    Row(
        modifier =
            modifier
                .fillMaxWidth()
                .border(1.dp, OpsColor.Border)
                .padding(horizontal = 12.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            modifier = Modifier.weight(1f).padding(end = 12.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = label,
                color = OpsColor.Ink,
                fontWeight = FontWeight.SemiBold,
                fontSize = 13.sp,
            )
            if (detail != null) {
                OpsBodyText(text = detail)
            }
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors =
                SwitchDefaults.colors(
                    checkedThumbColor = Color.White,
                    checkedTrackColor = OpsColor.Accent,
                    uncheckedThumbColor = Color.White,
                    uncheckedTrackColor = OpsColor.BorderMuted,
                ),
        )
    }
}

@Composable
fun OpsBottomNav(
    selected: ConsoleTab,
    onSelected: (ConsoleTab) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier =
            modifier
                .fillMaxWidth()
                .border(1.dp, OpsColor.Border)
                .background(Color.White),
    ) {
        ConsoleTab.entries.forEach { tab ->
            val active = tab == selected
            val label =
                when (tab) {
                    ConsoleTab.AGENTS -> "Agents"
                    ConsoleTab.GUIDEBOOKS -> "Guidebooks"
                    ConsoleTab.SESSIONS -> "Sessions"
                }
            Box(
                modifier =
                    Modifier
                        .weight(1f)
                        .background(if (active) OpsColor.Accent else Color.White)
                        .clickable { onSelected(tab) }
                        .padding(vertical = 12.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = label.uppercase(),
                    color = if (active) Color.White else OpsColor.Ink,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    fontSize = 11.sp,
                )
            }
        }
    }
}
